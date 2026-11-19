"""Database migration and initial seed data for EduEval AI."""
import logging
from sqlalchemy import text, inspect
from app.core.database import engine, SessionLocal
from app.models.models import Base

logger = logging.getLogger(__name__)

def _seed_rtlp_library(db, AssessmentType, RubricVersion):
    """Seed every RTLP Chapter-14 assessment type with its rubric (idempotent).

    Existing types are linked to their RTLP code; a new rubric version is created only
    when the stored active criteria differ from the policy, so assessments that already
    reference an older version keep it.
    """
    from app.services.rubrics.library import library

    def signature(criteria):
        return [(c.get("name"), float(c.get("max_marks", 0)),
                 tuple((l.get("name"), l.get("description")) for l in c.get("levels", []) or []))
                for c in criteria or []]

    for item in library():
        atype = db.query(AssessmentType).filter(AssessmentType.name == item["name"]).first()
        if not atype:
            atype = AssessmentType(
                name=item["name"], description=item["description"], max_marks=item["total_marks"],
                default_discrepancy_threshold=0.20, is_active=True,
            )
            db.add(atype)
            db.flush()
            logger.info(f"Seeded RTLP assessment type {item['code']} {item['name']}")
        atype.rtlp_code = item["code"]
        atype.category = item["category"]
        atype.evaluation_mode = item["evaluation_mode"]
        if not atype.description:
            atype.description = item["description"]

        active = db.query(RubricVersion).filter(
            RubricVersion.assessment_type_id == atype.id, RubricVersion.is_active == True
        ).order_by(RubricVersion.version.desc()).first()
        if active and signature(active.criteria_data) == signature(item["criteria"]):
            continue
        latest = db.query(RubricVersion).filter(
            RubricVersion.assessment_type_id == atype.id
        ).order_by(RubricVersion.version.desc()).first()
        for rv in db.query(RubricVersion).filter(RubricVersion.assessment_type_id == atype.id).all():
            rv.is_active = False
        db.add(RubricVersion(
            assessment_type_id=atype.id,
            version=(latest.version + 1) if latest else 1,
            total_marks=item["total_marks"],
            is_active=True,
            criteria_data=item["criteria"],
        ))
        atype.max_marks = item["total_marks"]
        logger.info(f"RTLP rubric version created for {item['name']}")


def _backfill_assessment_subjects(db):
    """Every assessment is mapped to at least its original subject; submissions remember it."""
    from app.models.models import Assessment, AssessmentSubject, StudentSubmission

    for a in db.query(Assessment).all():
        if a.subject_id and not db.query(AssessmentSubject).filter(
                AssessmentSubject.assessment_id == a.id, AssessmentSubject.subject_id == a.subject_id).first():
            db.add(AssessmentSubject(assessment_id=a.id, subject_id=a.subject_id))
    db.flush()
    for sub in db.query(StudentSubmission).filter(StudentSubmission.subject_id.is_(None)).all():
        if sub.assessment:
            sub.subject_id = sub.assessment.subject_id


def run_migrations_and_seed():
    """Ensure all required columns and initial assessment types exist in the database."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Step 1: Create all tables defined in models if not exist
    Base.metadata.create_all(bind=engine)

    # Step 2: Backward-compatible column additions for existing tables
    with engine.connect() as conn:
        # Check assessments table columns
        if "assessments" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("assessments")]
            if "assessment_type_id" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN assessment_type_id INTEGER REFERENCES assessment_types(id)"))
            if "rubric_version_id" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN rubric_version_id INTEGER REFERENCES rubric_versions(id)"))
            if "instructions" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN instructions TEXT"))
            if "start_date" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN start_date DATETIME"))
            if "allowed_file_types" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN allowed_file_types VARCHAR(255) DEFAULT 'pdf,docx,doc,pptx,ppt,txt,images'"))
            if "discrepancy_threshold" not in columns:
                conn.execute(text("ALTER TABLE assessments ADD COLUMN discrepancy_threshold FLOAT DEFAULT 0.20"))

        # Check student_submissions table columns
        if "student_submissions" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("student_submissions")]
            if "submission_type" not in columns:
                conn.execute(text("ALTER TABLE student_submissions ADD COLUMN submission_type VARCHAR(50) DEFAULT 'upload'"))
            if "typed_content" not in columns:
                conn.execute(text("ALTER TABLE student_submissions ADD COLUMN typed_content TEXT"))
            if "submission_version" not in columns:
                conn.execute(text("ALTER TABLE student_submissions ADD COLUMN submission_version INTEGER DEFAULT 1"))
            if "is_draft" not in columns:
                conn.execute(text("ALTER TABLE student_submissions ADD COLUMN is_draft BOOLEAN DEFAULT 0"))
            if "rubric_version_id" not in columns:
                conn.execute(text("ALTER TABLE student_submissions ADD COLUMN rubric_version_id INTEGER REFERENCES rubric_versions(id)"))

        # Check ai_evaluations table columns
        if "ai_evaluations" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("ai_evaluations")]
            if "rubric_version_id" not in columns:
                conn.execute(text("ALTER TABLE ai_evaluations ADD COLUMN rubric_version_id INTEGER REFERENCES rubric_versions(id)"))
            if "error_details" not in columns:
                conn.execute(text("ALTER TABLE ai_evaluations ADD COLUMN error_details TEXT"))
            if "ai_criterion_scores_json" not in columns:
                conn.execute(text("ALTER TABLE ai_evaluations ADD COLUMN ai_criterion_scores_json JSON"))
            if "ai_irrelevant_observations_json" not in columns:
                conn.execute(text("ALTER TABLE ai_evaluations ADD COLUMN ai_irrelevant_observations_json JSON"))
            if "ai_status" not in columns:
                conn.execute(text("ALTER TABLE ai_evaluations ADD COLUMN ai_status VARCHAR(50) DEFAULT 'pending'"))

        # Columns added for the RTLP rubric library and the annotated feedback document
        additions = {
            "assessment_types": [("rtlp_code", "VARCHAR(20)"), ("category", "VARCHAR(50)"),
                                 ("evaluation_mode", "VARCHAR(30) DEFAULT 'document'")],
            "assessments": [("course_unit", "VARCHAR(255)"), ("reference_answer", "TEXT"),
                            ("rubric_data", "JSON"), ("rubric_source", "VARCHAR(50)"),
                            ("evaluation_mode", "VARCHAR(30)"), ("created_by_id", "INTEGER REFERENCES users(id)")],
            "student_submissions": [("subject_id", "INTEGER REFERENCES subjects(id)")],
            "faculty_evaluations": [("criterion_marks", "JSON")],
            "ai_evaluations": [("segments_json", "JSON"), ("annotations_json", "JSON")],
            "final_evaluations": [("final_criterion_scores", "JSON"), ("feedback_document", "JSON")],
        }
        for table, cols in additions.items():
            if table in existing_tables:
                present = {c["name"] for c in inspector.get_columns(table)}
                for name, ddl in cols:
                    if name not in present:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

        # Check course_profiles table columns
        if "course_profiles" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("course_profiles")]
            if "title" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN title VARCHAR(255)"))
            if "units_topics" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN units_topics JSON"))
            if "learning_materials" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN learning_materials TEXT"))
            if "reference_content" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN reference_content TEXT"))
            if "additional_info" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN additional_info TEXT"))
            if "is_typed_published" not in columns:
                conn.execute(text("ALTER TABLE course_profiles ADD COLUMN is_typed_published BOOLEAN DEFAULT 0"))

        conn.commit()

    # Step 3: Seed initial assessment types and rubric versions
    db = SessionLocal()
    try:
        from app.models.models import AssessmentType, RubricVersion, Assessment

        _seed_rtlp_library(db, AssessmentType, RubricVersion)
        _backfill_assessment_subjects(db)

        # Backfill any existing assessments that match names
        for assess in db.query(Assessment).all():
            if not assess.rubric_version_id and assess.assessment_type:
                legacy_type = assess.assessment_type.lower()
                name_map = {
                    "journal": "Reflective Journal",
                    "reflective": "Reflective Journal",
                    "assignment": "Free Writing",
                    "writing": "Free Writing",
                    "report": "Free Writing",
                }
                mapped_name = next(
                    (name for key, name in name_map.items() if key in legacy_type),
                    assess.assessment_type,
                )
                match_type = db.query(AssessmentType).filter(
                    AssessmentType.name.ilike(f"%{mapped_name}%")
                ).first()
                if match_type:
                    rv = db.query(RubricVersion).filter(
                        RubricVersion.assessment_type_id == match_type.id,
                        RubricVersion.is_active == True
                    ).first()
                    if rv:
                        assess.assessment_type_id = match_type.id
                        assess.rubric_version_id = rv.id

        db.commit()
    finally:
        db.close()
