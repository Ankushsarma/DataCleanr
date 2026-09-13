import concurrent.futures
from typing import Callable, Any
import json
import uuid

def log_to_db(db, job_id, message):
    from app.db.models import JobLog
    try:
        # Encode to ASCII safely so Windows console doesn't crash on Unicode characters
        safe_message = message.encode('ascii', errors='replace').decode('ascii')
        print(safe_message)
    except Exception:
        pass
    if job_id and db:
        try:
            db.add(JobLog(job_id=job_id, message=message))
            db.commit()
        except Exception as e:
            pass

# A simple local executor for background tasks without Celery/Redis
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def run_background_task(task_func: Callable, *args, **kwargs) -> concurrent.futures.Future:
    return executor.submit(task_func, *args, **kwargs)

def task_profile_dataset(dataset_id: str, file_path: str):
    """
    Background task to run the Deterministic Profiler and Issue Detector.
    """
    from app.services.profiler import PolarsProfiler
    from app.services.detector import IssueDetector
    from app.db.session import SessionLocal
    from app.db.models import Dataset, Issue, Job, CandidateModel
    from app.services.policy import policy_engine
    from app.services.selection import SelectionEngine
    from app.services.sandbox import SandboxExecutor
    from app.services.validator import ValidationEngine
    from app.models.ir import TransformationIR
    
    print(f"Starting background profiling for {dataset_id}...")
    
    try:
        # Run Profiler
        profiler_output = PolarsProfiler.profile(file_path)
        
        # Run Detector
        detected_issues = IssueDetector.detect(profiler_output, file_path=file_path)
        
        db = SessionLocal()
        
        # 1. Update Dataset with schema
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        if dataset:
            dataset.schema_json = profiler_output
            dataset.row_count = profiler_output.get("row_count")
            dataset.column_count = profiler_output.get("column_count")
        
        # 2. Create a Job to track this run
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            dataset_id=dataset_id,
            mode="AUTONOMOUS",
            state="RUNNING",
            policy_version="v1",
            profiler_version="1.0",
            agent_version="none",
            ir_schema_version="1.0",
            compiler_version="1.0"
        )
        db.add(job)
        db.commit() # commit instead of flush to release lock
        
        
        # Collect all winning IRs for the sandbox execution
        selected_irs = []
        
        from app.services.rule_engine import RuleBasedStrategyEngine
        from app.models.ir import IRCandidate
        
        # --- ISSUE LOOP (Rule-Based — no LLM calls needed) ---
        for di in detected_issues:
            issue = Issue(
                issue_id=str(uuid.uuid4()),
                job_id=job_id,
                column_name=di.column,
                issue_type=di.issue_type,
                evidence_ref=json.dumps(di.evidence),
                decision=None,
                final_state="PENDING"
            )
            db.add(issue)
            db.commit()
            
            # --- RULE-BASED STRATEGY SELECTION ---
            log_to_db(db, job_id, f"[Rule Engine] Resolving strategy for '{di.column}' ({di.issue_type})...")
            
            candidate_irs = RuleBasedStrategyEngine.resolve(
                issue_id=issue.issue_id,
                issue_column=di.column,
                issue_type=di.issue_type,
                issue_evidence=di.evidence,
                profiler_output=profiler_output,
            )
            
            candidates = [IRCandidate(ir=ir) for ir in candidate_irs]
            
            candidate_models = []
            for c in candidates:
                policy_result = policy_engine.evaluate(c.ir, profiler_output)
                if not policy_result.eligible:
                    log_to_db(db, job_id, f"  Policy Engine rejected {c.ir.operation.value}: {policy_result.violations}")
                else:
                    log_to_db(db, job_id, f"  Policy Engine approved {c.ir.operation.value}.")
                    
                candidate_record = CandidateModel(
                    candidate_id=str(uuid.uuid4()),
                    issue_id=issue.issue_id,
                    strategy=c.ir.operation.value,
                    ir_json=c.ir.model_dump(mode="json"),
                    agent_confidence=c.ir.agent_confidence,
                    agent_rationale=c.ir.rationale,
                    risk_level=c.ir.risk_level,
                    policy_eligible=policy_result.eligible,
                    selected=False
                )
                candidate_models.append(candidate_record)
                
            # --- CONTROL TRACK: Selection Engine ---
            selection_result = SelectionEngine.select(candidate_models)
            log_to_db(db, job_id, f"  Selection: {selection_result.decision} → {selection_result.selected_candidate.strategy if selection_result.selected_candidate else 'None'}")
            
            if selection_result.selected_candidate:
                winning_ir = next((c.ir for c in candidates if c.ir.operation.value == selection_result.selected_candidate.strategy), None)
                if winning_ir:
                    selected_irs.append(winning_ir)
                    selection_result.selected_candidate.selected = True
            
            db.add_all(candidate_models)
            db.commit()
        
        # Check for high risk
        has_high_risk = any(ir.risk_level == 'HIGH' for ir in selected_irs)
        
        if selected_irs and has_high_risk:
            log_to_db(db, job_id, "HIGH risk operations detected. Pausing for human approval.")
            job.state = "PENDING_APPROVAL"
        elif any(c.selected for c in db.query(CandidateModel).join(Issue).filter(Issue.job_id == job_id).all()):
            log_to_db(db, job_id, "Only LOW/MEDIUM risk operations detected. Proceeding to execution (Autonomous Mode)...")
            job.state = "EXECUTING"
            db.commit()
            
            selected_irs = [TransformationIR(**c.ir_json) for c in db.query(CandidateModel).join(Issue).filter(Issue.job_id == job_id, CandidateModel.selected == True).all()]
            
            max_retries = 3
            retry_count = 0
            validation_passed = False
            
            while retry_count <= max_retries:
                log_to_db(db, job_id, f"Executing approved AI strategies (Attempt {retry_count + 1})...")
                output_file = SandboxExecutor.execute(dataset_id, file_path, selected_irs)
                
                log_to_db(db, job_id, "Running independent Validation Engine...")
                validation_result = ValidationEngine.validate(file_path, output_file, selected_irs)
                if validation_result.passed:
                    log_to_db(db, job_id, "Validation PASSED. Generating output profile...")
                    validation_passed = True
                    try:
                        out_profile = PolarsProfiler.profile(output_file)
                        job.output_schema_json = out_profile
                    except Exception as e:
                        log_to_db(db, job_id, f"Failed to profile output file: {e}")
                    job.state = "COMPLETED"
                    job.applied_operations = job.applied_operations + [f"Applied: {ir.operation.value} to {ir.target_column}" for ir in selected_irs]
                    break
                else:
                    log_to_db(db, job_id, f"Validation FAILED: {validation_result.violations}")
                    retry_count += 1
                    if retry_count <= max_retries:
                        log_to_db(db, job_id, f"Triggering Retry {retry_count}/{max_retries}. Banning failed candidates...")
                        # MVP sim: mark FAILED since mock agent can't replan dynamically.
                        job.state = "FAILED"
                        break
                    else:
                        log_to_db(db, job_id, "Max retries exceeded.")
                        job.state = "FAILED"
                        break
                        
            if not validation_passed and job.state != "FAILED":
                job.state = "COMPLETED"
        else:
            job.state = "COMPLETED" # Completed but with no changes
            
        # Update metrics for the job
        # For MVP we simulate cost
        if 'job' in locals():
            job.cost_usd = 0.05 * len(detected_issues)  # simulated $0.05 per issue
            job.tokens_used = 1250 * len(detected_issues)
            job.llm_calls = len(detected_issues)
            from datetime import datetime
            job.ended_at = datetime.utcnow()
            db.commit()
            
        db.close()
        
        log_to_db(db, job_id, f"Finished profiling {dataset_id}. Detected {len(detected_issues)} issues.")
        
        # Display detailed results in terminal
        print("\n--- PROFILING RESULTS ---")
        print(f"Total Rows: {profiler_output.get('row_count')}")
        print(f"Total Columns: {profiler_output.get('column_count')}")
        
        if detected_issues:
            print("\n--- DETECTED ISSUES ---")
            for idx, di in enumerate(detected_issues, 1):
                print(f"{idx}. Column: {di.column} | Issue: {di.issue_type}")
                print(f"   Evidence: {di.evidence}")
        print("-------------------------\n")
        
        return {"status": "success", "issues_detected": len(detected_issues)}
        
    except Exception as e:
        print(f"Error profiling dataset {dataset_id}: {e}")
        if 'job' in locals():
            job.state = "FAILED"
            db.commit()
        if 'db' in locals():
            db.close()
        return {"status": "error", "message": str(e)}

def task_execute_job(dataset_id: str, job_id: str):
    """
    Executes a job that was previously stuck in PENDING_APPROVAL.
    """
    from app.db.session import SessionLocal
    from app.db.models import Job, Issue, CandidateModel, Dataset
    from app.services.sandbox import SandboxExecutor
    from app.services.validator import ValidationEngine
    from app.models.ir import TransformationIR
    
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        file_path = dataset.raw_s3_uri.replace("local://", "")
        
        job.state = "EXECUTING"
        db.commit()
        
        max_retries = 3
        retry_count = 0
        validation_passed = False
        
        while retry_count <= max_retries:
            issues = db.query(Issue).filter(Issue.job_id == job_id).all()
            selected_irs = []
            
            for i in issues:
                selected_candidate = db.query(CandidateModel).filter(
                    CandidateModel.issue_id == i.issue_id,
                    CandidateModel.selected == True
                ).first()
                
                if selected_candidate:
                    # Reconstruct IR
                    ir = TransformationIR(**selected_candidate.ir_json)
                    selected_irs.append(ir)
                    
            if not selected_irs:
                log_to_db(db, job_id, "No eligible candidates remaining to execute.")
                break
                
            log_to_db(db, job_id, f"Executing approved AI strategies (Attempt {retry_count + 1})...")
            output_file = SandboxExecutor.execute(dataset_id, file_path, selected_irs)
            log_to_db(db, job_id, f"Dataset successfully cleaned and saved to: {output_file}")
            
            # --- VALIDATION TRACK ---
            log_to_db(db, job_id, "Running independent Validation Engine...")
            validation_result = ValidationEngine.validate(file_path, output_file, selected_irs)
            
            if validation_result.passed:
                log_to_db(db, job_id, "Validation PASSED. Generating output profile...")
                validation_passed = True
                try:
                    from app.services.profiler import PolarsProfiler
                    out_profile = PolarsProfiler.profile(output_file)
                    job.output_schema_json = out_profile
                except Exception as e:
                    log_to_db(db, job_id, f"Failed to profile output file: {e}")
                job.state = "COMPLETED"
                break
            else:
                log_to_db(db, job_id, f"Validation FAILED: {validation_result.violations}")
                retry_count += 1
                if retry_count <= max_retries:
                    log_to_db(db, job_id, f"Triggering Retry {retry_count}/{max_retries}. Banning failed candidates...")
                    # For MVP, simply fail the job if validation fails. 
                    # True replanning with the MockAgent requires generating new IRs.
                    # We will mark it as FAILED here to simulate safe termination on failure.
                    job.state = "FAILED"
                    break
                else:
                    log_to_db(db, job_id, "Max retries exceeded.")
                    job.state = "FAILED"
                    break
            
        if not validation_passed and job.state != "FAILED":
            job.state = "COMPLETED" # No changes made
            
        from datetime import datetime
        job.ended_at = datetime.utcnow()
        db.commit()
        db.close()
        
    except Exception as e:
        print(f"Error executing approved job: {e}")
        if 'job' in locals():
            job.state = "FAILED"
            db.commit()
        if 'db' in locals():
            db.close()
