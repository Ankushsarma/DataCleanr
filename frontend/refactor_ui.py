import re

with open('src/app/page.tsx', 'r') as f:
    content = f.read()

# Add states
states = "  const [jobLogs, setJobLogs] = useState<any[]>([]);\n"
content = content.replace('  const [edaData', states + '  const [edaData')

# Add polling for logs
log_poll = """
    const pollLogs = async () => {
      if (!datasetId || !datasetResults?.job?.job_id) return;
      if (datasetResults.job.state === 'RUNNING' || datasetResults.job.state === 'EXECUTING') {
        try {
          const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/jobs/${datasetResults.job.job_id}/logs`);
          if (res.ok) {
            const data = await res.json();
            setJobLogs(data.logs);
          }
        } catch (e) { console.error(e); }
      }
    };
    if (isPolling) {
      pollLogs();
      const logInterval = setInterval(pollLogs, 1000);
      return () => clearInterval(logInterval);
    }
"""

use_effect_logs = """
  useEffect(() => {
""" + log_poll + """
  }, [datasetId, datasetResults?.job?.job_id, datasetResults?.job?.state, isPolling]);
"""

content = content.replace('  useEffect(() => {\n    if (!datasetId || !datasetResults) return;\n    \n    const fetchEda', use_effect_logs + '\n  useEffect(() => {\n    if (!datasetId || !datasetResults) return;\n    \n    const fetchEda')

# Add the UI for Terminal and Applied Operations
ui_components = """
                  {/* Live Terminal Logs */}
                  {(datasetResults.job?.state === "RUNNING" || datasetResults.job?.state === "EXECUTING") && (
                    <div className="bg-slate-900 rounded-xl p-4 mb-8 font-mono text-sm shadow-lg border border-slate-700">
                      <div className="flex items-center gap-2 mb-3 border-b border-slate-700 pb-2">
                        <div className="w-3 h-3 rounded-full bg-red-500"></div>
                        <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                        <div className="w-3 h-3 rounded-full bg-slate-500"></div>
                        <span className="text-slate-400 ml-2">Live Execution Logs</span>
                      </div>
                      <div className="h-48 overflow-y-auto custom-scrollbar flex flex-col justify-end">
                        {jobLogs.length === 0 ? (
                          <div className="text-slate-500">Waiting for logs...</div>
                        ) : (
                          jobLogs.map((log, idx) => (
                            <div key={idx} className="text-emerald-400 mb-1">
                              <span className="text-slate-500 mr-2">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                              {log.message}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {/* Applied Operations Tracker */}
                  {viewMode === 'AFTER' && datasetResults.job?.applied_operations?.length > 0 && (
                    <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 mb-8">
                      <h4 className="text-lg font-medium text-slate-800 mb-4 flex items-center gap-2">
                        <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" /></svg>
                        Applied Operations Tracker
                      </h4>
                      <ul className="space-y-3">
                        {datasetResults.job.applied_operations.map((op: string, idx: number) => (
                          <li key={idx} className="flex items-start gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-sm">
                            <span className="w-6 h-6 rounded-full bg-orange-500/10 text-orange-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{idx + 1}</span>
                            <span className="text-slate-700 text-sm">{op}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
"""

content = content.replace('                  {/* Toggle Switch */}', ui_components + '\n                  {/* Toggle Switch */}')

with open('src/app/page.tsx', 'w') as f:
    f.write(content)
print('Updated page.tsx')
