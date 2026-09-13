import re

with open('src/app/page.tsx', 'r') as f:
    content = f.read()

# 1. State Additions
states = """  const [isScalingModalOpen, setIsScalingModalOpen] = useState(false);
  const [scaleMethod, setScaleMethod] = useState('Standard');
  const [scaleStatus, setScaleStatus] = useState('');
  const [hasScaledData, setHasScaledData] = useState(false);
  
  const [isTransformModalOpen, setIsTransformModalOpen] = useState(false);
  const [transformMethod, setTransformMethod] = useState('Log1p');
  const [transformStatus, setTransformStatus] = useState('');
  const [hasTransformedData, setHasTransformedData] = useState(false);
"""
content = content.replace('  const [hasBalancedData, setHasBalancedData] = useState(false);', '  const [hasBalancedData, setHasBalancedData] = useState(false);\n' + states)

# 2. Handlers Additions
handlers = """
  const handleScale = async () => {
    if (!datasetId || encodingColumns.length === 0) return;
    setScaleStatus('Scaling dataset... please wait.');
    try {
      const targetCols = encodingColumns.map(c => c.column);
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/scale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_columns: targetCols, method: scaleMethod })
      });
      if (res.ok) {
        setHasScaledData(true);
        setIsScalingModalOpen(false);
        setScaleStatus('');
        setViewMode('BEFORE'); setTimeout(() => setViewMode('AFTER'), 100);
      } else {
        const errorData = await res.json();
        setScaleStatus(`Error: ${errorData.detail}`);
      }
    } catch (e) { setScaleStatus('Error connecting to backend.'); }
  };

  const handleTransform = async () => {
    if (!datasetId || encodingColumns.length === 0) return;
    setTransformStatus('Transforming dataset... please wait.');
    try {
      const targetCols = encodingColumns.map(c => c.column);
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/transform`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_columns: targetCols, method: transformMethod })
      });
      if (res.ok) {
        setHasTransformedData(true);
        setIsTransformModalOpen(false);
        setTransformStatus('');
        setViewMode('BEFORE'); setTimeout(() => setViewMode('AFTER'), 100);
      } else {
        const errorData = await res.json();
        setTransformStatus(`Error: ${errorData.detail}`);
      }
    } catch (e) { setTransformStatus('Error connecting to backend.'); }
  };
"""
content = content.replace('  const handleFileSelect', handlers + '\n  const handleFileSelect')

# 3. Add Stepper UI
stepper_ui = """
      {/* 8-Step Pipeline Stepper */}
      {datasetId && (
        <div className="max-w-6xl mx-auto w-full mb-8">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
              ML Data Preparation Pipeline
            </h3>
            
            <div className="relative">
              <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-100 -translate-y-1/2 z-0 rounded-full"></div>
              <div className="absolute top-1/2 left-0 h-1 bg-orange-500 -translate-y-1/2 z-0 rounded-full transition-all duration-500" 
                style={{ width: `${
                  hasBalancedData ? 100 : 
                  hasScaledData ? 85 : 
                  hasTransformedData ? 70 : 
                  hasEncodedData ? 55 : 
                  datasetResults?.job?.state === 'COMPLETED' ? 40 : 0
                }%` }}>
              </div>
              
              <div className="flex justify-between relative z-10">
                {/* Auto Steps */}
                <div className="flex flex-col items-center group">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${datasetResults?.job?.state === 'COMPLETED' ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-slate-200 text-slate-500'}`}>1</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Format</span>
                </div>
                <div className="flex flex-col items-center group">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${datasetResults?.job?.state === 'COMPLETED' ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-slate-200 text-slate-500'}`}>2</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Impute</span>
                </div>
                <div className="flex flex-col items-center group">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${datasetResults?.job?.state === 'COMPLETED' ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-slate-200 text-slate-500'}`}>3</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Deduplicate</span>
                </div>
                <div className="flex flex-col items-center group">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${datasetResults?.job?.state === 'COMPLETED' ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-slate-200 text-slate-500'}`}>4</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Outliers</span>
                </div>
                
                {/* Manual Steps */}
                <div className="flex flex-col items-center group cursor-pointer" onClick={() => datasetResults?.job?.state === 'COMPLETED' && !hasEncodedData && fetchEncodingData()}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${hasEncodedData ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : datasetResults?.job?.state === 'COMPLETED' ? 'bg-white border-2 border-orange-500 text-orange-500 animate-pulse' : 'bg-slate-200 text-slate-500'}`}>5</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Encode</span>
                </div>
                <div className="flex flex-col items-center group cursor-pointer" onClick={() => hasEncodedData && !hasTransformedData && setIsTransformModalOpen(true)}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${hasTransformedData ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : hasEncodedData ? 'bg-white border-2 border-orange-500 text-orange-500 animate-pulse' : 'bg-slate-200 text-slate-500'}`}>6</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Transform</span>
                </div>
                <div className="flex flex-col items-center group cursor-pointer" onClick={() => hasTransformedData && !hasScaledData && setIsScalingModalOpen(true)}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${hasScaledData ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : hasTransformedData ? 'bg-white border-2 border-orange-500 text-orange-500 animate-pulse' : 'bg-slate-200 text-slate-500'}`}>7</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Scale</span>
                </div>
                <div className="flex flex-col items-center group cursor-pointer" onClick={() => hasScaledData && !hasBalancedData && setIsBalancingModalOpen(true)}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${hasBalancedData ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : hasScaledData ? 'bg-white border-2 border-orange-500 text-orange-500 animate-pulse' : 'bg-slate-200 text-slate-500'}`}>8</div>
                  <span className="text-xs font-medium mt-2 text-slate-600">Balance</span>
                </div>
              </div>
            </div>
            <div className="mt-4 text-xs text-slate-500 flex justify-between">
              <span>Automated AI Execution</span>
              <span>Interactive Processing</span>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace('      {/* Main Content */}', stepper_ui + '\n      {/* Main Content */}')

# 4. Add Buttons to the After view toolbar
buttons = """
                <button
                  onClick={() => setIsTransformModalOpen(true)}
                  disabled={!hasEncodedData}
                  className="px-6 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-full font-medium transition-colors text-sm shadow-md"
                >
                  Transform
                </button>
                <button
                  onClick={() => setIsScalingModalOpen(true)}
                  disabled={!hasTransformedData}
                  className="px-6 py-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-full font-medium transition-colors text-sm shadow-md"
                >
                  Scale
                </button>
"""
# Replace the old Balance Dataset button cluster with a mapped out array of sequential buttons
old_buttons = """                <button
                  onClick={() => setIsBalancingModalOpen(true)}
                  disabled={!hasEncodedData}
                  className="px-8 py-3 ml-4 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-full font-medium transition-colors shadow-lg shadow-slate-900/25"
                >
                  Balance Dataset
                </button>"""

new_buttons = """                <button
                  onClick={() => setIsTransformModalOpen(true)}
                  disabled={!hasEncodedData || hasTransformedData}
                  className="px-6 py-3 ml-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white rounded-full font-medium text-sm shadow-lg shadow-slate-900/25"
                >
                  6. Transform
                </button>
                <button
                  onClick={() => setIsScalingModalOpen(true)}
                  disabled={!hasTransformedData || hasScaledData}
                  className="px-6 py-3 ml-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white rounded-full font-medium text-sm shadow-lg shadow-slate-900/25"
                >
                  7. Scale
                </button>
                <button
                  onClick={() => setIsBalancingModalOpen(true)}
                  disabled={!hasScaledData || hasBalancedData}
                  className="px-6 py-3 ml-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white rounded-full font-medium text-sm shadow-lg shadow-slate-900/25"
                >
                  8. Balance
                </button>"""
content = content.replace(old_buttons, new_buttons)

# Also rename "Generate Encodings" to "5. Encode"
content = content.replace('>                  Generate Encodings', '>                  5. Encode')
content = content.replace('disabled={encodingColumns.length === 0}', 'disabled={encodingColumns.length === 0 || hasEncodedData}')

# 5. Add Modals
modals = """
      {/* Transformation Modal */}
      {isTransformModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg">
            <h3 className="text-xl font-bold text-slate-800 mb-4">Transform Numerical Data</h3>
            <p className="text-slate-600 mb-6 text-sm">
              Apply a mathematical transformation to reduce skewness and stabilize variance across numerical features.
            </p>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 mb-2">Transformation Method</label>
              <select 
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800"
                value={transformMethod}
                onChange={(e) => setTransformMethod(e.target.value)}
              >
                <option value="Log1p">Log Transformation (Log1p) - Best for right-skewed data</option>
                <option value="Sqrt">Square Root - Best for counts</option>
              </select>
            </div>

            {transformStatus && (
              <div className="mb-6 p-4 bg-slate-100 rounded-xl text-slate-700 text-sm font-medium animate-pulse">
                {transformStatus}
              </div>
            )}

            <div className="flex justify-end gap-3 mt-8">
              <button
                onClick={() => setIsTransformModalOpen(false)}
                className="px-6 py-2.5 rounded-full font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleTransform}
                disabled={!!transformStatus}
                className="px-6 py-2.5 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-white rounded-full font-medium"
              >
                Apply Transform
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Scaling Modal */}
      {isScalingModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg">
            <h3 className="text-xl font-bold text-slate-800 mb-4">Scale Numerical Data</h3>
            <p className="text-slate-600 mb-6 text-sm">
              Bring all numerical features into the same range or distribution to optimize machine learning performance.
            </p>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 mb-2">Scaling Method</label>
              <select 
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800"
                value={scaleMethod}
                onChange={(e) => setScaleMethod(e.target.value)}
              >
                <option value="Standard">Standardization (Z-Score) - Mean 0, Std 1</option>
                <option value="MinMax">Normalization (Min-Max) - Bounds [0, 1]</option>
              </select>
            </div>

            {scaleStatus && (
              <div className="mb-6 p-4 bg-slate-100 rounded-xl text-slate-700 text-sm font-medium animate-pulse">
                {scaleStatus}
              </div>
            )}

            <div className="flex justify-end gap-3 mt-8">
              <button
                onClick={() => setIsScalingModalOpen(false)}
                className="px-6 py-2.5 rounded-full font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleScale}
                disabled={!!scaleStatus}
                className="px-6 py-2.5 bg-orange-500 hover:bg-orange-400 disabled:opacity-50 text-white rounded-full font-medium"
              >
                Apply Scaling
              </button>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace('      {/* Balancing Modal */}', modals + '\n      {/* Balancing Modal */}')

# 6. Update EDA useEffect dependencies
content = content.replace('hasEncodedData, hasBalancedData]);', 'hasEncodedData, hasTransformedData, hasScaledData, hasBalancedData]);')


with open('src/app/page.tsx', 'w') as f:
    f.write(content)
print('Updated page.tsx with 8-step pipeline')
