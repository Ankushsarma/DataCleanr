import re

with open('backend/worker/tasks.py', 'r') as f:
    content = f.read()

# Add log_to_db
log_func = '''
def log_to_db(db, job_id, message):
    from app.db.models import JobLog
    print(message)
    if job_id and db:
        try:
            db.add(JobLog(job_id=job_id, message=message))
            db.commit()
        except Exception as e:
            print(f"Failed to save log: {e}")
'''

content = content.replace('import uuid\n', 'import uuid\n' + log_func)

# Replace prints with log_to_db in task_profile_dataset
content = content.replace('print(f"[Rule Engine] Resolving strategy', 'log_to_db(db, job_id, f"[Rule Engine] Resolving strategy')
content = content.replace('print(f"  Policy Engine rejected', 'log_to_db(db, job_id, f"  Policy Engine rejected')
content = content.replace('print(f"  Policy Engine approved', 'log_to_db(db, job_id, f"  Policy Engine approved')
content = content.replace('print(f"  Selection: {selection_result', 'log_to_db(db, job_id, f"  Selection: {selection_result')
content = content.replace('print("HIGH risk operations detected.', 'log_to_db(db, job_id, "HIGH risk operations detected.')
content = content.replace('print("Only LOW/MEDIUM risk operations detected.', 'log_to_db(db, job_id, "Only LOW/MEDIUM risk operations detected.')
content = content.replace('print(f"Executing approved AI strategies', 'log_to_db(db, job_id, f"Executing approved AI strategies')
content = content.replace('print("Running independent Validation Engine...")', 'log_to_db(db, job_id, "Running independent Validation Engine...")')
content = content.replace('print("Validation PASSED.', 'log_to_db(db, job_id, "Validation PASSED.')
content = content.replace('print(f"Failed to profile output file:', 'log_to_db(db, job_id, f"Failed to profile output file:')
content = content.replace('print(f"Validation FAILED:', 'log_to_db(db, job_id, f"Validation FAILED:')
content = content.replace('print(f"Triggering Retry', 'log_to_db(db, job_id, f"Triggering Retry')
content = content.replace('print("Max retries exceeded.")', 'log_to_db(db, job_id, "Max retries exceeded.")')
content = content.replace('print(f"Finished profiling', 'log_to_db(db, job_id, f"Finished profiling')

# Record applied operations for rule engine
content = content.replace('job.state = "COMPLETED"\n                    break', 'job.state = "COMPLETED"\n                    job.applied_operations = job.applied_operations + [f"Applied: {ir.operation.value} to {ir.target_column}" for ir in selected_irs]\n                    break')
content = content.replace('job.state = "COMPLETED" # Completed but with no changes', 'job.state = "COMPLETED" # Completed but with no changes')

# For task_execute_job, we need to pass db and job_id
content = content.replace('print("No eligible candidates', 'log_to_db(db, job_id, "No eligible candidates')
content = content.replace('print(f"Dataset successfully cleaned', 'log_to_db(db, job_id, f"Dataset successfully cleaned')

with open('backend/worker/tasks.py', 'w') as f:
    f.write(content)
print('Refactored tasks.py.')
