from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
import os
import hashlib
import json
from datetime import datetime

from app.db.session import get_db
from app.db.models import Dataset, Job, Issue
from worker.tasks import run_background_task, task_profile_dataset, task_execute_job

router = APIRouter()

# Create a local storage directory for the MVP
STORAGE_DIR = "local_storage/raw"
os.makedirs(STORAGE_DIR, exist_ok=True)

@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported in MVP.")
    
    # Read file content for hashing
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Save file to local storage (simulating S3 for now)
    dataset_id = str(uuid.uuid4())
    file_path = os.path.join(STORAGE_DIR, f"{dataset_id}.csv")
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    # Basic schema and metadata (In reality, the Profiler Worker would do this)
    # For now we stub it out until the profiler is implemented.
    schema_json = {"status": "pending_profiling"}
    
    # Create DB entry
    dataset = Dataset(
        dataset_id=dataset_id,
        namespace_id="default_namespace",
        raw_s3_uri=f"local://{file_path}",
        raw_hash=file_hash,
        schema_json=schema_json,
        row_count=None,
        column_count=None,
        created_by="anonymous_user",
        created_at=datetime.utcnow()
    )
    
    # We create tables if they don't exist since this is SQLite MVP
    from app.db.models import Base
    from app.db.session import engine
    Base.metadata.create_all(bind=engine)

    db.add(dataset)
    db.commit()
    
    # Trigger background profiling task
    run_background_task(task_profile_dataset, dataset_id, file_path)
    
    return {
        "message": "Dataset uploaded and profiling started successfully",
        "dataset_id": dataset_id,
        "filename": file.filename
    }

@router.get("/{dataset_id}")
def get_dataset_results(dataset_id: str, db: Session = Depends(get_db)):
    from app.db.models import CandidateModel
    
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    job = db.query(Job).filter(Job.dataset_id == dataset_id).order_by(Job.started_at.desc()).first()
    issues = []
    issues_payload = []
    
    if job:
        issues = db.query(Issue).filter(Issue.job_id == job.job_id).all()
        for i in issues:
            # Get the selected candidate for this issue
            selected_candidate = db.query(CandidateModel).filter(
                CandidateModel.issue_id == i.issue_id,
                CandidateModel.selected == True
            ).first()
            
            candidate_payload = None
            if selected_candidate:
                candidate_payload = {
                    "strategy": selected_candidate.strategy,
                    "rationale": selected_candidate.agent_rationale,
                    "confidence": selected_candidate.agent_confidence,
                    "risk_level": selected_candidate.risk_level
                }
                
            issues_payload.append({
                "issue_id": i.issue_id,
                "column_name": i.column_name,
                "issue_type": i.issue_type,
                "evidence_ref": i.evidence_ref,
                "candidate": candidate_payload
            })
        
    return {
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "schema_json": dataset.schema_json
        },
        "job": {
            "job_id": job.job_id if job else None,
            "state": job.state if job else "PENDING",
            "output_schema_json": job.output_schema_json if job else None
        },
        "issues": issues_payload
    }

@router.get("/{dataset_id}/download")
def download_dataset(dataset_id: str):
    file_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Cleaned dataset not found. Job may not be completed yet.")
    
    return FileResponse(
        path=file_path,
        media_type="text/csv",
        filename=f"autoclean_{dataset_id[:8]}.csv"
    )

@router.post("/{dataset_id}/jobs/{job_id}/approve")
def approve_job(dataset_id: str, job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.job_id == job_id, Job.dataset_id == dataset_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.state != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Job is in state {job.state}, cannot approve.")
        
    job.state = "APPROVED"
    db.commit()
    
    run_background_task(task_execute_job, dataset_id, job_id)
    
    return {"message": "Job approved and execution started"}
    
@router.get("/audit")
def get_audit_logs(db: Session = Depends(get_db)):
    # Get all jobs, ordered by most recent
    jobs = db.query(Job).order_by(Job.started_at.desc()).limit(50).all()
    audit_data = []
    
    for job in jobs:
        dataset = db.query(Dataset).filter(Dataset.dataset_id == job.dataset_id).first()
        
        # Get all candidates for this job
        issues = db.query(Issue).filter(Issue.job_id == job.job_id).all()
        issue_ids = [i.issue_id for i in issues]
        
        audit_data.append({
            "job_id": job.job_id,
            "dataset_id": job.dataset_id,
            "filename": "dataset.csv" if not dataset else "dataset.csv", # Placeholder since we don't store original filename directly on dataset in this MVP yet
            "state": job.state,
            "started_at": job.started_at,
            "ended_at": job.ended_at,
            "cost_usd": float(job.cost_usd) if job.cost_usd else 0.0,
            "tokens_used": job.tokens_used or 0,
            "llm_calls": job.llm_calls or 0,
            "policy_version": job.policy_version,
            "issues_count": len(issues)
        })
        
    return audit_data
