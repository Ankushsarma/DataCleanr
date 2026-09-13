import re

with open('src/app/page.tsx', 'r') as f:
    content = f.read()

# Add states for balancing
states = """  const [isBalancingModalOpen, setIsBalancingModalOpen] = useState(false);
  const [balanceStatus, setBalanceStatus] = useState('');
  const [hasBalancedData, setHasBalancedData] = useState(false);
"""
content = content.replace('  const [hasEncodedData', states + '  const [hasEncodedData')

# Add fetch function for balancing
balance_funcs = """
  const handleBalance = async () => {
    if (!datasetId || !targetColumn) return;
    setBalanceStatus('Balancing dataset with SMOTE... please wait.');
    
    try {
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/balance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_column: targetColumn })
      });
      
      if (res.ok) {
        setHasBalancedData(true);
        setIsBalancingModalOpen(false);
        setBalanceStatus('');
        // Trigger a re-fetch of EDA
        setViewMode('BEFORE'); 
        setTimeout(() => setViewMode('AFTER'), 100);
      } else {
        const errorData = await res.json();
        setBalanceStatus(`Error: ${errorData.detail}`);
      }
    } catch (e) {
      setBalanceStatus('Error connecting to backend.');
    }
  };
"""

content = content.replace('  const handleFileSelect', balance_funcs + '\n  const handleFileSelect')

# Add "Balance Dataset" button next to "Generate Encodings"
buttons_search = '''                <button
                  onClick={applyEncoding}
                  disabled={encodingColumns.length === 0}
                  className="px-8 py-3 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-full font-medium transition-colors shadow-lg shadow-orange-500/25"
                >
                  Generate Encodings
                </button>'''

balance_btn = buttons_search + '''
                <button
                  onClick={() => setIsBalancingModalOpen(true)}
                  disabled={!hasEncodedData}
                  className="px-8 py-3 ml-4 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-full font-medium transition-colors shadow-lg shadow-slate-900/25"
                >
                  Balance Dataset
                </button>'''
content = content.replace(buttons_search, balance_btn)

# Add Balancing Modal
modal_search = '      {/* Encoding Modal */}'

balance_modal = """
      {/* Balancing Modal */}
      {isBalancingModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg">
            <h3 className="text-xl font-bold text-slate-800 mb-4">Balance Dataset (SMOTE)</h3>
            <p className="text-slate-600 mb-6 text-sm">
              Select the numeric target class you wish to balance. SMOTE will generate synthetic minority samples.
            </p>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 mb-2">Target Column</label>
              <select 
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-orange-500"
                value={targetColumn}
                onChange={(e) => setTargetColumn(e.target.value)}
              >
                <option value="">-- Select Target Column --</option>
                {encodingColumns.map((col: any) => (
                  <option key={col.column} value={col.column}>{col.column}</option>
                ))}
              </select>
            </div>

            {balanceStatus && (
              <div className="mb-6 p-4 bg-slate-100 rounded-xl text-slate-700 text-sm font-medium animate-pulse">
                {balanceStatus}
              </div>
            )}

            <div className="flex justify-end gap-3 mt-8">
              <button
                onClick={() => setIsBalancingModalOpen(false)}
                className="px-6 py-2.5 rounded-full font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleBalance}
                disabled={!targetColumn || !!balanceStatus}
                className="px-6 py-2.5 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-white rounded-full font-medium transition-colors shadow-lg shadow-orange-500/25"
              >
                Apply SMOTE
              </button>
            </div>
          </div>
        </div>
      )}
"""

content = content.replace(modal_search, balance_modal + '\n' + modal_search)

# Also update the re-fetch EDA to use hasBalancedData
content = content.replace('}, [datasetId, datasetResults, viewMode, hasEncodedData]);', '}, [datasetId, datasetResults, viewMode, hasEncodedData, hasBalancedData]);')

with open('src/app/page.tsx', 'w') as f:
    f.write(content)
print('Updated page.tsx with Balancing modal')
