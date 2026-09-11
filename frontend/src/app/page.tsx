"use client";

import React, { useState, useRef, useEffect } from 'react';

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [datasetResults, setDatasetResults] = useState<any>(null);
  const [viewMode, setViewMode] = useState<'BEFORE' | 'AFTER'>('BEFORE');
  const [activeTab, setActiveTab] = useState<'DASHBOARD' | 'AUDIT'>('DASHBOARD');
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isEncodingModalOpen, setIsEncodingModalOpen] = useState(false);
  const [encodingColumns, setEncodingColumns] = useState<any[]>([]);
  const [targetColumn, setTargetColumn] = useState<string>('');
  const [encodingStatus, setEncodingStatus] = useState('');
  const [hasEncodedData, setHasEncodedData] = useState(false);
  const [hasPromptedEncoding, setHasPromptedEncoding] = useState(false);
  const [edaData, setEdaData] = useState<any>(null);
  const [isEdaLoading, setIsEdaLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    const pollResults = async () => {
      if (!datasetId || !isPolling) return;

      try {
        const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}`);
        if (res.ok) {
          const data = await res.json();
          setDatasetResults(data);

          if (data.job?.state === "PENDING_APPROVAL") {
            setIsPolling(false);
            setUploadStatus('Action Required: High Risk Approvals Pending');
          } else if (data.job?.state === "COMPLETED") {
            setIsPolling(false);
            setUploadStatus('Profiling Complete & Auto-Cleaned!');
            if (!hasEncodedData && !hasPromptedEncoding) {
              setHasPromptedEncoding(true);
              fetchEncodingData();
            }
          } else if (data.job?.state === "FAILED") {
            setIsPolling(false);
            setUploadStatus('Job Failed.');
          }
        }
      } catch (error) {
        console.error("Failed to fetch results", error);
      }
    };

    if (isPolling) {
      pollResults();
      interval = setInterval(pollResults, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [datasetId, isPolling]);

  useEffect(() => {
    if (!datasetId || !datasetResults) return;
    
    const fetchEda = async () => {
      setIsEdaLoading(true);
      const stateParam = viewMode === 'BEFORE' ? 'raw' : 'encoded';
      try {
        const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/eda?state=${stateParam}`);
        if (res.ok) {
          const data = await res.json();
          setEdaData(data);
        } else {
          setEdaData(null);
        }
      } catch (e) {
        console.error(e);
        setEdaData(null);
      }
      setIsEdaLoading(false);
    };
    
    fetchEda();
  }, [datasetId, datasetResults, viewMode, hasEncodedData]);

  const approveJob = async () => {
    if (!datasetId || !datasetResults?.job?.job_id) return;
    setUploadStatus('Approving and executing...');

    try {
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/jobs/${datasetResults.job.job_id}/approve`, {
        method: 'POST'
      });
      if (res.ok) {
        setIsPolling(true); // resume polling
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchEncodingData = async () => {
    if (!datasetId) return;
    setEncodingStatus('Analyzing columns...');
    setIsEncodingModalOpen(true);
    
    try {
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/encoding/analyze`);
      if (res.ok) {
        const data = await res.json();
        setEncodingColumns(data.columns);
        setEncodingStatus('');
      } else {
        setEncodingStatus('Failed to analyze columns.');
      }
    } catch (e) {
      setEncodingStatus('Error connecting to backend.');
    }
  };

  const applyEncoding = async () => {
    if (!datasetId) return;
    setEncodingStatus('Generating encodings with LLM... please wait.');
    
    try {
      const res = await fetch(`http://localhost:8000/api/v1/datasets/${datasetId}/encoding/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_column_name: targetColumn || null })
      });
      
      if (res.ok) {
        setHasEncodedData(true);
        setIsEncodingModalOpen(false);
        setEncodingStatus('');
      } else {
        setEncodingStatus('Failed to apply encodings.');
      }
    } catch (e) {
      setEncodingStatus('Error connecting to backend.');
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const uploadFile = async () => {
    if (!file) return;
    setUploadStatus('Uploading...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8000/api/v1/datasets/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setUploadStatus(`Upload Success! Profiling...`);
        setDatasetId(data.dataset_id);
        setIsPolling(true);
        setDatasetResults(null);
        setHasEncodedData(false);
        setHasPromptedEncoding(false);
      } else {
        const err = await res.json();
        setUploadStatus(`Error: ${err.detail || 'Upload failed'}`);
      }
    } catch (error) {
      setUploadStatus('Error: Could not connect to backend');
    }
  };

  const loadAuditLogs = async () => {
    setActiveTab('AUDIT');
    try {
      const res = await fetch('http://localhost:8000/api/v1/datasets/audit');
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <main className="bg-gradient-mesh min-h-screen flex flex-col items-center p-8 lg:p-24 relative overflow-hidden">

      {/* Decorative background elements */}
      {/* Header */}
      <header className="w-full max-w-6xl flex justify-between items-center mb-16 z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center shadow-lg shadow-orange-500/30">
            <svg className="w-6 h-6 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            AutoClean<span className="text-orange-500">AI</span>
          </h1>
        </div>

        <nav className="hidden md:flex gap-8 text-sm font-medium text-slate-600">
          <a href="#" onClick={() => setActiveTab('DASHBOARD')} className={`transition-colors duration-200 ${activeTab === 'DASHBOARD' ? 'text-orange-500 font-bold' : 'hover:text-slate-900'}`}>Dashboard</a>
          <a href="#" className="hover:text-slate-900 transition-colors duration-200">Datasets</a>
          <a href="#" className="hover:text-slate-900 transition-colors duration-200">Policies</a>
          <a href="#" onClick={loadAuditLogs} className={`transition-colors duration-200 ${activeTab === 'AUDIT' ? 'text-orange-500 font-bold' : 'hover:text-slate-900'}`}>Audit Logs</a>
        </nav>

        <button className="px-5 py-2 rounded-full text-sm font-medium bg-white border border-slate-200 hover:bg-slate-50 transition-all duration-300">
          Sign In
        </button>
      </header>

      {/* DASHBOARD VIEW */}
      {activeTab === 'DASHBOARD' && (
        <>
          {/* Hero Section */}
          <div className="z-10 flex flex-col items-center text-center max-w-3xl mb-16 animate-float">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-600 text-xs font-medium mb-6">
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              Single-Agent Engine v6.0 Active
            </div>
            <h2 className="text-5xl lg:text-6xl font-extrabold tracking-tight mb-6 leading-tight">
              Intelligent Data Cleaning <br />
              <span className="text-slate-900">
                Driven by Evidence.
              </span>
            </h2>
            <p className="text-lg text-slate-500 max-w-2xl">
              Upload your raw dataset. Our reasoning agent analyzes the deterministic evidence, proposes safe transformations, and executes them in an isolated sandbox.
            </p>
          </div>

          {/* Upload Component */}
          <div className="z-10 w-full max-w-4xl">
            <div
              className={`glass-panel rounded-3xl p-10 transition-all duration-300 transform ${isDragging ? 'scale-[1.02] border-orange-500 shadow-orange-500/20' : 'hover:border-white/20'
                }`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <div className="border-2 border-dashed border-slate-300 rounded-2xl p-12 flex flex-col items-center justify-center text-center group hover:border-orange-500/50 hover:bg-orange-500/5 transition-all duration-300 cursor-pointer"
                onClick={() => fileInputRef.current?.click()}>

                <input
                  type="file"
                  className="hidden"
                  accept=".csv"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                />

                <div className="w-20 h-20 mb-6 rounded-full bg-slate-50 flex items-center justify-center group-hover:scale-110 group-hover:bg-orange-500/20 transition-transform duration-500">
                  <svg className="w-10 h-10 text-slate-500 group-hover:text-orange-500 transition-colors duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>

                <h3 className="text-xl font-semibold mb-2">
                  {file ? file.name : "Upload your dataset"}
                </h3>

                <p className="text-slate-500 text-sm mb-6 max-w-sm">
                  {file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB - Click to change file` : "Drag and drop your CSV file here, or click to browse. Max file size: 2GB (up to 10M rows)."}
                </p>

                <div className="flex gap-4">
                  <button
                    className={`px-8 py-3 rounded-full font-medium transition-colors duration-300 flex items-center gap-2 shadow-lg ${file ? 'bg-slate-200 hover:bg-slate-300 text-slate-800' : 'animate-glow bg-orange-500 hover:bg-orange-400 text-white shadow-orange-500/25'}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (file) { setFile(null); setUploadStatus(''); }
                      else { fileInputRef.current?.click(); }
                    }}
                  >
                    {file ? "Clear" : "Select File"}
                    {!file && <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>}
                  </button>

                  {file && (
                    <button
                      className="animate-glow px-8 py-3 rounded-full bg-orange-500 hover:bg-orange-400 text-white font-medium transition-colors duration-300 flex items-center gap-2 shadow-lg shadow-orange-500/25"
                      onClick={(e) => { e.stopPropagation(); uploadFile(); }}
                    >
                      Upload & Analyze
                    </button>
                  )}
                </div>

                {uploadStatus && (
                  <div className={`mt-6 p-3 rounded-lg text-sm w-full max-w-md ${uploadStatus.includes('Success') ? 'bg-slate-900/20 text-slate-900 border border-slate-900/30' : uploadStatus.includes('Uploading') ? 'bg-orange-500/20 text-orange-600' : 'bg-red-500/20 text-red-300 border border-red-500/30'}`}>
                    {uploadStatus}
                  </div>
                )}
              </div>
            </div>

            {/* Results Section */}
            {datasetResults && (
              <div className="z-10 w-full max-w-4xl mt-8 transition-all duration-500 opacity-100">
                <div className="glass-panel rounded-3xl p-8 border border-orange-500/30 bg-white/80 backdrop-blur-md shadow-2xl">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-2xl font-semibold flex items-center gap-3">
                      <span className="w-8 h-8 rounded-full bg-orange-500/20 text-orange-500 flex items-center justify-center">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      </span>
                      Profiling Results
                    </h3>

                    <div className="flex gap-3">
                      {datasetResults.job?.state === "PENDING_APPROVAL" && (
                        <button
                          onClick={approveJob}
                          className="flex items-center gap-2 px-6 py-2 bg-orange-500 hover:bg-orange-500 text-slate-900 rounded-xl transition-all shadow-lg shadow-orange-500/20 font-bold text-sm animate-pulse"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Approve HIGH Risk Operations
                        </button>
                      )}

                      {datasetResults.job?.state === "COMPLETED" && (
                        <div className="flex gap-2">
                          {hasEncodedData ? (
                            <button
                              onClick={() => window.open(`http://localhost:8000/api/v1/datasets/${datasetId}/encoding/download_encoded`, '_blank')}
                              className="flex items-center gap-2 px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-500 border border-orange-500/30 rounded-xl transition-colors shadow-lg font-medium text-sm"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                              Download Encoded Data
                            </button>
                          ) : (
                            <button
                              onClick={() => window.open(`http://localhost:8000/api/v1/datasets/${datasetId}/download`, '_blank')}
                              className="flex items-center gap-2 px-4 py-2 bg-slate-900/20 hover:bg-slate-900/30 text-slate-900 border border-slate-900/30 rounded-xl transition-colors shadow-lg shadow-slate-900/10 font-medium text-sm"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                              Download Cleaned Dataset
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-8">
                    <div className="bg-orange-500 rounded-xl p-6 shadow-lg shadow-orange-500/30">
                      <p className="text-white/80 text-sm mb-1 uppercase tracking-wider font-semibold">Total Rows</p>
                      <p className="text-3xl font-bold text-white">
                        {viewMode === 'BEFORE'
                          ? datasetResults.dataset?.schema_json?.row_count?.toLocaleString()
                          : (datasetResults.job?.output_schema_json?.row_count?.toLocaleString() || datasetResults.dataset?.schema_json?.row_count?.toLocaleString())}
                      </p>
                    </div>
                    <div className="bg-slate-900 rounded-xl p-6 shadow-lg shadow-slate-900/30">
                      <p className="text-slate-400 text-sm mb-1 uppercase tracking-wider font-semibold">Total Columns</p>
                      <p className="text-3xl font-bold text-white">
                        {viewMode === 'BEFORE'
                          ? datasetResults.dataset?.schema_json?.column_count?.toLocaleString()
                          : (datasetResults.job?.output_schema_json?.column_count?.toLocaleString() || datasetResults.dataset?.schema_json?.column_count?.toLocaleString())}
                      </p>
                    </div>
                  </div>

                  {/* Toggle Switch */}
                  {datasetResults.job?.output_schema_json && (
                    <div className="flex justify-center mb-8">
                      <div className="bg-white p-1 rounded-full flex gap-1 border border-slate-200">
                        <button
                          onClick={() => setViewMode('BEFORE')}
                          className={`px-6 py-2 rounded-full text-sm font-semibold transition-all ${viewMode === 'BEFORE' ? 'bg-orange-500 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}
                        >
                          Before Cleaning
                        </button>
                        <button
                          onClick={() => setViewMode('AFTER')}
                          className={`px-6 py-2 rounded-full text-sm font-semibold transition-all ${viewMode === 'AFTER' ? 'bg-slate-900 text-white shadow-lg' : 'text-slate-500 hover:text-slate-800'}`}
                        >
                          After Cleaning
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Detected Issues / Resolution Status */}
                  {viewMode === 'BEFORE' ? (
                    datasetResults.issues?.length > 0 ? (
                      <div>
                        <h4 className="text-lg font-medium text-slate-600 mb-4 flex justify-between items-end">
                          Detected Issues
                          <span className="text-xs bg-red-500/20 text-red-500 px-3 py-1 rounded-full border border-red-500/30 shadow-[0_0_10px_rgba(244,63,94,0.2)]">{datasetResults.issues.length} found</span>
                        </h4>
                        <div className="space-y-4 max-h-[700px] overflow-y-auto pr-2 custom-scrollbar">
                          {datasetResults.issues.map((issue: any, idx: number) => (
                            <div key={issue.issue_id} className="bg-slate-50 rounded-xl p-5 border border-red-500/20 hover:border-red-500/40 hover:bg-white transition-all duration-300">
                              {/* Issue Header */}
                              <div className="flex flex-col sm:flex-row justify-between items-start mb-3 gap-3">
                                <div className="flex items-center gap-3">
                                  <span className="w-7 h-7 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center text-sm font-mono shadow-inner">{idx + 1}</span>
                                  <span className="font-semibold text-slate-900 text-lg">{issue.column_name}</span>
                                </div>
                                <span className="px-3 py-1 rounded-full text-xs font-semibold bg-red-500/10 text-red-500 border border-red-500/20 tracking-wide">
                                  {issue.issue_type}
                                </span>
                              </div>
                              {/* Evidence */}
                              <div className="bg-slate-100 rounded-lg p-3 mt-2 border border-slate-200 mb-4">
                                <p className="text-xs text-slate-600 font-mono break-words leading-relaxed">
                                  <span className="text-slate-500 mr-2">Evidence:</span>
                                  {issue.evidence_ref}
                                </p>
                              </div>
                              {/* AI Candidate Strategy */}
                              {issue.candidate ? (
                                <div className="bg-indigo-900/20 border border-orange-500/30 rounded-xl p-4 mt-2">
                                  <div className="flex justify-between items-center mb-3">
                                    <h5 className="text-orange-600 font-semibold flex items-center gap-2">
                                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                                      Selected Strategy
                                    </h5>
                                    <div className="flex gap-2">
                                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase border ${issue.candidate.risk_level === 'HIGH' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                                          issue.candidate.risk_level === 'MEDIUM' ? 'bg-orange-500/20 text-orange-500 border-orange-500/30' :
                                            'bg-slate-900/20 text-slate-900 border-slate-900/30'
                                        }`}>
                                        Risk: {issue.candidate.risk_level}
                                      </span>
                                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase border ${issue.candidate.confidence === 'HIGH' ? 'bg-slate-900/20 text-slate-900 border-slate-900/30' :
                                          issue.candidate.confidence === 'MEDIUM' ? 'bg-orange-500/20 text-orange-500 border-orange-500/30' :
                                            'bg-red-500/20 text-red-400 border-red-500/30'
                                        }`}>
                                        Conf: {issue.candidate.confidence}
                                      </span>
                                    </div>
                                  </div>
                                  <div className="mb-3">
                                    <span className="inline-block px-3 py-1 rounded-md bg-orange-500 text-white text-sm font-mono font-medium shadow-lg shadow-orange-500/20">
                                      {issue.candidate.strategy}
                                    </span>
                                  </div>
                                  <p className="text-sm text-slate-600 leading-relaxed italic border-l-2 border-orange-500/50 pl-3 py-1">
                                    "{issue.candidate.rationale}"
                                  </p>
                                </div>
                              ) : (
                                <div className="bg-white0 border border-slate-200 rounded-xl p-4 mt-2 flex items-center justify-center gap-2">
                                  <span className="w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin"></span>
                                  <span className="text-sm text-slate-500">Agent reasoning in progress...</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="bg-slate-900/10 border border-slate-900/20 rounded-xl p-8 text-center flex flex-col items-center justify-center gap-3">
                        <svg className="w-12 h-12 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        <p className="text-slate-900 font-medium text-lg">No issues detected! Your data is completely clean.</p>
                      </div>
                    )
                  ) : (
                    <div className="bg-slate-900/10 border border-slate-900/20 rounded-xl p-8 text-center flex flex-col items-center justify-center gap-3 mb-8 shadow-[0_0_20px_rgba(16,185,129,0.15)]">
                      <svg className="w-12 h-12 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <h4 className="text-slate-900 font-bold text-xl">Cleaning Successful</h4>
                      <p className="text-emerald-200/70 font-medium max-w-lg">
                        All {datasetResults.issues?.length || 0} detected issues have been safely resolved. The dataset has been validated and saved. Scroll down to see the updated profile report.
                      </p>
                    </div>
                  )}

                  {/* Complete Profiling Report */}
                  {datasetResults.dataset?.schema_json?.columns && (
                    <div className="mt-10 pt-8 border-t border-slate-200">
                      <h4 className="text-xl font-medium text-slate-800 mb-6 flex items-center gap-2">
                        <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                        Complete Profiling Report
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {Object.entries(viewMode === 'BEFORE' ? datasetResults.dataset.schema_json.columns : (datasetResults.job?.output_schema_json?.columns || datasetResults.dataset.schema_json.columns)).map(([colName, stats]: [string, any]) => (
                          <div key={colName} className="bg-slate-50 rounded-xl p-5 border border-slate-200 hover:border-orange-500/40 hover:bg-white/60 transition-all duration-300">
                            <div className="flex justify-between items-center mb-4">
                              <span className="font-semibold text-slate-900 truncate max-w-[150px] text-lg tracking-wide" title={colName}>{colName}</span>
                              <span className="px-2.5 py-1.5 rounded-lg bg-orange-500/10 text-orange-600 text-xs font-mono border border-orange-500/20">{stats.dtype}</span>
                            </div>
                            <div className="space-y-3 text-sm">
                              <div className="flex justify-between text-slate-500">
                                <span>Unique Values</span>
                                <span className="text-slate-900 font-medium bg-slate-100/50 px-2 py-0.5 rounded">{stats.n_unique}</span>
                              </div>
                              <div className="flex justify-between text-slate-500">
                                <span>Missing</span>
                                <span className={`font-medium px-2 py-0.5 rounded ${stats.null_count > 0 ? 'text-orange-500 bg-orange-500/10' : 'text-slate-900 bg-slate-100/50'}`}>
                                  {stats.null_count} ({stats.null_pct}%)
                                </span>
                              </div>
                              {stats.mean !== undefined && (
                                <div className="flex justify-between text-slate-500">
                                  <span>Mean</span>
                                  <span className="text-slate-900 font-medium bg-slate-100/50 px-2 py-0.5 rounded">{Number(stats.mean).toFixed(2)}</span>
                                </div>
                              )}
                              {stats.min !== undefined && stats.max !== undefined && (
                                <div className="flex justify-between text-slate-500">
                                  <span>Range</span>
                                  <span className="text-slate-900 font-medium bg-slate-100/50 px-2 py-0.5 rounded text-xs">{Number(stats.min).toFixed(1)} - {Number(stats.max).toFixed(1)}</span>
                                </div>
                              )}
                              {stats.most_frequent !== undefined && (
                                <div className="flex justify-between text-slate-500 items-center">
                                  <span>Most Freq</span>
                                  <span className="text-slate-900 font-medium bg-slate-100/50 px-2 py-0.5 rounded truncate max-w-[90px] text-xs" title={String(stats.most_frequent)}>{String(stats.most_frequent)}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* EDA Dashboard */}
                  {datasetResults.dataset?.schema_json?.columns && (
                    <div className="mt-10 pt-8 border-t border-slate-200">
                      <h4 className="text-xl font-medium text-slate-800 mb-6 flex items-center gap-2">
                        <svg className="w-5 h-5 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>
                        Exploratory Data Analysis
                      </h4>
                      
                      {isEdaLoading ? (
                        <div className="flex justify-center items-center py-12">
                          <div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                        </div>
                      ) : edaData ? (
                        <div className="space-y-8">
                          {/* Correlation Heatmap */}
                          {edaData.heatmap_image && (
                            <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 flex flex-col items-center">
                              <h5 className="text-lg font-medium text-slate-900 mb-4 w-full text-left">Correlation Heatmap (Numeric)</h5>
                              <img 
                                src={`data:image/png;base64,${edaData.heatmap_image}`} 
                                alt="Correlation Heatmap" 
                                className="max-w-full rounded-lg shadow-lg"
                              />
                            </div>
                          )}
                          
                          {/* Distributions */}
                          {edaData.distributions_image && (
                            <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 flex flex-col items-center">
                              <h5 className="text-lg font-medium text-slate-900 mb-4 w-full text-left">Feature Distributions</h5>
                              <div className="w-full overflow-x-auto custom-scrollbar flex justify-center">
                                <img 
                                  src={`data:image/png;base64,${edaData.distributions_image}`} 
                                  alt="Feature Distributions" 
                                  className="rounded-lg shadow-lg"
                                  style={{ minWidth: '800px' }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center p-8 text-slate-500 text-sm">Failed to load EDA data.</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Feature Highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
              {[
                { title: 'Deterministic Profiling', desc: 'No LLM hallucinations. Built on high-performance Polars engine.', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
                { title: 'Policy Constrained', desc: 'Strict UMR bounds and customizable safety policies keep data intact.', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
                { title: 'Immutable Audit Trail', desc: 'Full provenance logs from raw hash to transformed output.', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' },
              ].map((feature, i) => (
                <div key={i} className="glass-panel rounded-2xl p-6 hover:bg-slate-50 transition-colors duration-300">
                  <div className="w-10 h-10 rounded-lg bg-orange-500/20 text-orange-500 flex items-center justify-center mb-4">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={feature.icon} />
                    </svg>
                  </div>
                  <h4 className="text-slate-900 font-medium mb-2">{feature.title}</h4>
                  <p className="text-slate-500 text-sm leading-relaxed">{feature.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Audit Logs View */}
      {activeTab === 'AUDIT' && (
        <div className="z-10 w-full max-w-6xl mt-8">
          <h2 className="text-3xl font-bold text-slate-900 mb-8">System Audit Logs</h2>
          <div className="glass-panel rounded-3xl p-8 border border-slate-200 bg-white/80 backdrop-blur-md">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 text-sm uppercase tracking-wider">
                    <th className="p-4 font-medium">Job ID</th>
                    <th className="p-4 font-medium">State</th>
                    <th className="p-4 font-medium">Started At</th>
                    <th className="p-4 font-medium">Issues Found</th>
                    <th className="p-4 font-medium">LLM Cost</th>
                    <th className="p-4 font-medium">Tokens Used</th>
                  </tr>
                </thead>
                <tbody className="text-slate-800">
                  {auditLogs.map((log) => (
                    <tr key={log.job_id} className="border-b border-slate-200/20 hover:bg-slate-50 transition-colors">
                      <td className="p-4 font-mono text-sm text-orange-600">{log.job_id.split('-')[0]}</td>
                      <td className="p-4">
                        <span className={`px-2 py-1 rounded text-xs font-bold tracking-wider uppercase border ${log.state === 'COMPLETED' ? 'bg-slate-900/10 text-slate-900 border-slate-900/20' :
                            log.state === 'FAILED' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                              'bg-orange-500/10 text-orange-500 border-orange-500/20'
                          }`}>
                          {log.state}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-slate-500">{new Date(log.started_at).toLocaleString()}</td>
                      <td className="p-4 text-sm">{log.issues_count}</td>
                      <td className="p-4 text-sm text-slate-900 font-mono">${log.cost_usd.toFixed(2)}</td>
                      <td className="p-4 text-sm text-slate-500">{log.tokens_used.toLocaleString()}</td>
                    </tr>
                  ))}
                  {auditLogs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-slate-500">No jobs found in the audit log.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Encoding Modal */}
      {isEncodingModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-orange-500/30 rounded-3xl p-8 max-w-2xl w-full shadow-2xl relative max-h-[90vh] flex flex-col">
            <button onClick={() => setIsEncodingModalOpen(false)} className="absolute top-6 right-6 text-slate-500 hover:text-slate-900 transition-colors">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
            <h3 className="text-2xl font-bold text-slate-900 mb-2">Data Encoding</h3>
            <p className="text-slate-500 mb-6">Select which string columns should be treated as Categorical data for encoding. The LLM will determine the best encoding strategy (One-Hot or Label) for them.</p>
            
            {encodingStatus ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12">
                <div className="w-10 h-10 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-orange-600 font-medium animate-pulse">{encodingStatus}</p>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                <div className="mb-6 p-4 bg-slate-50 rounded-xl border border-orange-500/30">
                  <label className="block text-sm font-medium text-slate-600 mb-2">Target Variable (Optional, required for Target Encoding)</label>
                  <select 
                    value={targetColumn}
                    onChange={(e) => setTargetColumn(e.target.value)}
                    className="w-full bg-slate-100 border border-slate-600 text-slate-900 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-orange-500"
                  >
                    <option value="">None</option>
                    {datasetResults?.dataset?.schema_json?.columns && Object.keys(datasetResults.dataset.schema_json.columns).map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-3">
                  <h4 className="text-slate-500 font-medium text-sm mb-2">String Columns to be Analyzed:</h4>
                  {encodingColumns.length > 0 ? encodingColumns.map((col: any) => (
                    <div key={col.column} className="bg-slate-50 rounded-lg p-3 border border-slate-200 flex justify-between items-center">
                      <span className="font-semibold text-slate-900 text-sm">{col.column}</span>
                      <span className="text-xs text-slate-500">{col.unique_count} unique values</span>
                    </div>
                  )) : (
                    <div className="text-center p-4 text-slate-500 text-sm">No string columns found.</div>
                  )}
                </div>
              </div>
            )}
            
            {!encodingStatus && (
              <div className="mt-8 pt-6 border-t border-slate-200 flex justify-end">
                <button
                  onClick={applyEncoding}
                  disabled={encodingColumns.length === 0}
                  className="px-8 py-3 bg-orange-500 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed text-slate-900 rounded-full font-medium transition-colors shadow-lg shadow-orange-500/25"
                >
                  Generate Encodings
                </button>
              </div>
            )}
          </div>
        </div>
      )}

    </main>
  );
}
