# DataCleanr (AutoCleanAI) - Project Context

This document serves as a comprehensive snapshot of the DataCleanr project: detailing everything that has been implemented up to version 1.0.0, and outlining the features and technical debt remaining for future iterations.

## 🎯 What is Implemented (Current State)

### 1. Backend Engine (FastAPI & Polars)
- **Data Ingestion:** Upload CSV datasets via FastAPI, with automatic hashing and local storage management.
- **Autonomous Profiling:** Generates comprehensive dataset statistics (unique values, missing percentages, data types, min/max, mean) using `polars`.
- **Issue Detection & Resolution:** Automatically flags data quality issues (like nulls, anomalies) and generates Intermediate Representation (IR) strategies to fix them.
- **Smart Encoding Pipeline:** A dedicated LLM agent analyzes categorical/string columns, reviews unique values, and intelligently maps them to numeric formats (Label Encoding or One-Hot Encoding).
- **Execution Sandbox:** Compiles IR strategies into Polars LazyFrame operations for fast, memory-efficient data transformations.
- **Absolute Guarantee Pipeline:** A final, unskippable data imputation pass that guarantees 0 missing values in the final output (filling numbers with medians and strings with "Unknown").
- **Automated EDA (Exploratory Data Analysis):** Uses `matplotlib` and `seaborn` to dynamically generate Correlation Heatmaps and Feature Distributions, returning them as base64 images.
- **Database & Auditing:** SQLite integration (`SQLAlchemy`) to track jobs, issues, strategies, simulated costs (USD), and token usage.

### 2. Frontend Dashboard (Next.js & TailwindCSS)
- **Premium "Soft UI":** A custom-built, modern light-theme utilizing a strict White, Orange, and Black (Slate-900) color palette, complete with glassmorphic cards and soft shadows.
- **Interactive Data Pipeline:** 
  - Drag-and-drop file uploader.
  - State management for toggling between "Before Cleaning" (Raw) and "After Cleaning" (Transformed) metrics.
- **Visual EDA Displays:** Beautifully renders the backend-generated heatmaps and distribution graphs right in the browser.
- **Interactive Agent Modal:** A popup modal that pauses the pipeline to ask the user for specific column details (like selecting a target variable) before triggering the LLM Encoding agent.
- **Audit Logs:** A detailed table displaying past cleaning jobs, execution times, issues resolved, and token usage costs.

---

## 🚧 What is Left (Future Roadmap & Enhancements)

While the core autonomous pipeline is fully functional, several advanced features and production-ready architectures remain to be built:

### 1. Authentication & Multi-Tenancy
- The current "Sign In" button is a placeholder. 
- **To-Do:** Integrate NextAuth or Clerk for user authentication. Implement multi-tenancy so users can save and access their specific datasets across sessions securely.

### 2. Advanced Data Transformations
- **To-Do:** Expand the Rule Engine and LLM capabilities to handle:
  - **Outlier Detection:** Z-score or IQR-based outlier capping/removal.
  - **Date/Time Parsing:** Automatically detecting messy date strings (e.g., "12-Jan-25") and standardizing them into ISO-8601 timestamps.
  - **Text Normalization:** Lowercasing, removing special characters, and standardizing text features.

### 3. Production Infrastructure
- **To-Do:** Move away from `concurrent.futures.ThreadPoolExecutor` and SQLite.
  - Implement **Celery & Redis** for robust, scalable background job queues.
  - Migrate to **PostgreSQL** for database management.
  - Add **Docker & docker-compose** support for easy containerized deployments.

### 4. Customizable Policies
- **To-Do:** Build a frontend interface to allow users to upload or tweak their own `policy_v1.yaml` files. This would let users dictate specific constraints to the LLM (e.g., "Never drop rows", "Always use mean instead of median").

### 5. Export Options
- Currently, the app only supports downloading the cleaned data as a CSV.
- **To-Do:** Add support for downloading files as Parquet or JSON, and allow direct integration/export to cloud storage buckets (AWS S3, Google Cloud Storage) or data warehouses (Snowflake, BigQuery).
