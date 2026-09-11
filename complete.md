# AutoCleanAI — PRD v6.0 Implementation Status

Based on the Final Definition of Done (Section 36) and the Core Architecture (Section 11) described in the `AutoCleanAI_PRD_v6.0.md`, here is a breakdown of what has been implemented so far and what remains incomplete in the current codebase.

## ✅ Completed Parts
- **Upload a CSV:** The frontend accepts CSV file drag-and-drops and POSTs them to the backend API (`/api/v1/datasets/upload`).
- **Receive deterministic EDA:** The `PolarsProfiler` successfully parses the dataset, calculates column statistics, null counts, and unique values, and the results are returned and beautifully rendered on the frontend.
- **See detected data-quality issues:** The `IssueDetector` successfully identifies basic quality problems from the profile, saves them to the database, and they are displayed in the frontend Results Section.
- **Database Schema:** The initial models for `Dataset`, `Job`, `Issue`, and `CandidateModel` are defined and persist state using SQLite.

## ❌ Incomplete Parts (Pending Implementation)
- **Generate candidate strategies via the single reasoning agent:** Currently, the background worker detects issues and stops (setting the state to `PENDING_APPROVAL`). There is no actual LLM (e.g., AWS Bedrock) integration yet to generate cleaning strategies.
- **See why strategies were proposed:** The AI explanation and confidence scores are not yet generated or surfaced.
- **Policy Engine:** The deterministic policy filter to block unsafe candidates is not built.
- **Transformation IR & Sandbox Execution:** The system to compile the AI's intent into a structured Intermediate Representation and safely execute it in a sandbox does not exist yet.
- **Validation Engine:** Independent validation of the transformed data against preservation constraints is missing.
- **Deterministic Selection Engine:** The scoring algorithm (Validation + Preservation + Confidence - Penalties) to pick the best candidate is not implemented.
- **Retry Mechanism:** The agent does not yet support replanning or retrying failed transformations.
- **Review / Approve HIGH-risk transformations:** The UI and backend logic to allow an `Approver` to accept/reject a transformation is missing.
- **Download Final Dataset:** The ability for users to download the cleaned `.csv` is not yet available.
- **Access Control & Auth:** Roles (Viewer, Contributor, Approver, Admin) and namespaces are not enforced. There is no "Sign In" flow.
- **Audit & Versioning:** The provenance tracking and transformation history logs are not yet visible or fully recorded.
- **Cost Tracking:** Logging and displaying the LLM token usage and estimated cloud cost per job is not implemented.

---
*Note: The project is currently at Stage 1 / Stage 2 of the Rollout Strategy (Section 33). The data tracking and deterministic profiling foundations are in place, but the AI, control, execution, and platform tracks are pending.*
