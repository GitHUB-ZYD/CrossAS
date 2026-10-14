const FALLBACK_MODELS = [
    {id: "human-promoter", display_name: "Human Promoter"},
    {id: "human-enhancer", display_name: "Human Enhancer"},
    {id: "pig-promoter", display_name: "Pig Promoter"},
    {id: "pig-enhancer", display_name: "Pig Enhancer"}
];

const GENOME_LABELS = {
    human: "Human (GRCh38)",
    pig: "Pig (Sscrofa11.1)"
};

const CHROMS = {
    human: ["chr1","chr2","chr3","chr4","chr5","chr6","chr7","chr8","chr9","chr10","chr11","chr12","chr13","chr14","chr15","chr16","chr17","chr18","chr19","chr20","chr21","chr22","chrX","chrY"],
    pig: ["chr1","chr2","chr3","chr4","chr5","chr6","chr7","chr8","chr9","chr10","chr11","chr12","chr13","chr14","chr15","chr16","chr17","chr18","chrX","chrY","chrMT"]
};

const DISPLAY_HEADERS = {
    id: "Variant ID",
    genome: "Reference Genome",
    chrom: "Chromosome",
    start: "Start",
    end: "End",
    model: "Prediction Model",
    model_species: "Model Species",
    element_type: "Element Type",
    as_probability: "AS Probability",
    non_as_probability: "Non-AS Probability",
    prediction: "Prediction",
    status: "Status",
    error: "Error"
};

function apiBase() {
    return window.location.pathname.split("/static/")[0];
}

function formatProbability(value, digits = 4) {
    if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "-";
    return Number(value).toFixed(digits);
}

function formatPercent(value) {
    if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "-";
    return `${(Number(value) * 100).toFixed(2)}%`;
}

function GenomeSelect({value, onChange}) {
    return (
        <select value={value} onChange={e => onChange(e.target.value)}>
            <option value="pig">{GENOME_LABELS.pig}</option>
            <option value="human">{GENOME_LABELS.human}</option>
        </select>
    );
}

function ModelSelect({models, value, onChange}) {
    const available = models.length ? models : FALLBACK_MODELS;
    React.useEffect(() => {
        if (!available.some(model => model.id === value) && available.length) {
            onChange(available[0].id);
        }
    }, [models]);
    return (
        <select value={value} onChange={e => onChange(e.target.value)}>
            {available.map(model => (
                <option value={model.id} key={model.id}>{model.display_name || model.id}</option>
            ))}
        </select>
    );
}

function SingleVariantPrediction({models}) {
    const [genome, setGenome] = React.useState("pig");
    const [chrom, setChrom] = React.useState("chr1");
    const [start, setStart] = React.useState(130071886);
    const [model, setModel] = React.useState("pig-promoter");
    const [result, setResult] = React.useState(null);
    const [error, setError] = React.useState("");
    const [running, setRunning] = React.useState(false);

    React.useEffect(() => {
        if (!CHROMS[genome].includes(chrom)) setChrom("chr1");
    }, [genome]);

    async function runPrediction() {
        setRunning(true);
        setError("");
        setResult(null);
        try {
            const response = await fetch(`${apiBase()}/as_pred`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    genome,
                    chrom,
                    start: Number(start),
                    end: Number(start) + 1,
                    model
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Prediction failed.");
            setResult(data);
        } catch (e) {
            setError(e.message);
        } finally {
            setRunning(false);
        }
    }

    return (
        <div>
            <div className="grid-two">
                <section className="card">
                    <h2>Variant Input</h2>
                    <div className="form-group">
                        <label>Reference Genome</label>
                        <GenomeSelect value={genome} onChange={setGenome}/>
                    </div>
                    <div className="form-group">
                        <label>Chromosome</label>
                        <select value={chrom} onChange={e => setChrom(e.target.value)}>
                            {CHROMS[genome].map(x => <option value={x} key={x}>{x}</option>)}
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Start Position (0-based)</label>
                        <input type="number" min="0" value={start} onChange={e => setStart(e.target.value)}/>
                    </div>
                    <p className="help">CrossAS evaluates a one-base SNP interval: [start, start + 1).</p>
                </section>

                <section className="card">
                    <h2>Prediction Settings</h2>
                    <div className="form-group">
                        <label>Prediction Model</label>
                        <ModelSelect models={models} value={model} onChange={setModel}/>
                    </div>
                    <button className="primary" onClick={runPrediction} disabled={running}>
                        {running ? "Predicting..." : "Predict Variant"}
                    </button>
                </section>
            </div>

            {error && <div className="error-box">{error}</div>}

            <section className="card result-card">
                <h2>Prediction Result</h2>
                {!result ? <div className="muted">No prediction has been run yet.</div> : (
                    <div>
                        <div className="result-meta">
                            <div><span>Variant</span><strong>{result.genome} · {result.chrom}:{result.start}-{result.end}</strong></div>
                            <div><span>Prediction Model</span><strong>{result.model}</strong></div>
                            <div><span>Prediction</span><strong className="prediction-label">{result.prediction}</strong></div>
                        </div>
                        <div className="probability-grid">
                            <div className="probability-box">
                                <span>Allele-Specific Probability</span>
                                <strong>{formatPercent(result.as_probability)}</strong>
                                <small>{formatProbability(result.as_probability, 4)}</small>
                            </div>
                            <div className="probability-box">
                                <span>Non-Allele-Specific Probability</span>
                                <strong>{formatPercent(result.non_as_probability)}</strong>
                                <small>{formatProbability(result.non_as_probability, 4)}</small>
                            </div>
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}

function BatchVariantPrediction({models}) {
    const [file, setFile] = React.useState(null);
    const [genome, setGenome] = React.useState("pig");
    const [model, setModel] = React.useState("pig-promoter");
    const [batchSize, setBatchSize] = React.useState(32);
    const [results, setResults] = React.useState([]);
    const [summary, setSummary] = React.useState(null);
    const [error, setError] = React.useState("");
    const [running, setRunning] = React.useState(false);

    async function runBatch() {
        if (!file) {
            setError("Please select a TSV or CSV variant file first.");
            return;
        }
        setRunning(true);
        setError("");
        setResults([]);
        setSummary(null);
        try {
            const form = new FormData();
            form.append("file", file);
            form.append("genome", genome);
            form.append("model", model);
            form.append("batch_size", batchSize);
            const response = await fetch(`${apiBase()}/as_pred_batch`, {method: "POST", body: form});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Batch prediction failed.");
            setResults(data.results || []);
            setSummary(data.summary || null);
        } catch (e) {
            setError(e.message);
        } finally {
            setRunning(false);
        }
    }

    function valueForDownload(column, value) {
        if (value === null || value === undefined) return "";
        if (column === "as_probability" || column === "non_as_probability") {
            return Number(value).toFixed(6);
        }
        return String(value).replace(/\t/g, " ").replace(/\n/g, " ");
    }

    function downloadResults() {
        if (!results.length) return;
        const columns = Object.keys(results[0]);
        const text = [
            columns.join("\t"),
            ...results.map(row => columns.map(col => valueForDownload(col, row[col])).join("\t"))
        ].join("\n");
        const blob = new Blob([text], {type: "text/tab-separated-values;charset=utf-8"});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "crossas_batch_results.tsv";
        a.click();
        URL.revokeObjectURL(url);
    }

    function downloadTemplate() {
        const text = "id\tchrom\tstart\tend\nvariant_1\tchr1\t1000000\t1000001\nvariant_2\tchr2\t2000000\t2000001\n";
        const blob = new Blob([text], {type: "text/tab-separated-values;charset=utf-8"});
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "crossas_batch_template.tsv";
        a.click();
        URL.revokeObjectURL(url);
    }

    const preview = results.slice(0, 50);
    const preferredColumns = [
        "id", "genome", "chrom", "start", "end", "model",
        "as_probability", "non_as_probability", "prediction", "status", "error"
    ];
    const displayColumns = preview.length
        ? preferredColumns.filter(key => Object.prototype.hasOwnProperty.call(preview[0], key))
        : [];

    function displayCell(column, value) {
        if (value === null || value === undefined) return "";
        if (column === "as_probability" || column === "non_as_probability") return formatProbability(value, 4);
        return String(value);
    }

    return (
        <div>
            <div className="grid-two">
                <section className="card">
                    <h2>Variant File</h2>
                    <div className="form-group">
                        <label>Input File</label>
                        <input type="file" accept=".tsv,.txt,.csv,.bed" onChange={e => setFile(e.target.files[0] || null)}/>
                    </div>
                    <div className="form-group">
                        <label>Reference Genome</label>
                        <GenomeSelect value={genome} onChange={setGenome}/>
                    </div>
                    <div className="form-group">
                        <label>Batch Size</label>
                        <input type="number" min="1" value={batchSize} onChange={e => setBatchSize(e.target.value)}/>
                    </div>
                    <button className="secondary" onClick={downloadTemplate}>Download Input Template</button>
                    <p className="help">
                        Required columns: chromosome and start. End is optional and defaults to start + 1.
                        A genome column may be supplied per row; otherwise the selected Reference Genome is used.
                    </p>
                </section>

                <section className="card">
                    <h2>Prediction Settings</h2>
                    <div className="form-group">
                        <label>Prediction Model</label>
                        <ModelSelect models={models} value={model} onChange={setModel}/>
                    </div>
                    <button className="primary" onClick={runBatch} disabled={running}>
                        {running ? "Running..." : "Run Batch Prediction"}
                    </button>
                </section>
            </div>

            {error && <div className="error-box">{error}</div>}

            <section className="card">
                <div className="card-header-row">
                    <h2>Prediction Results</h2>
                    <button className="secondary" onClick={downloadResults} disabled={!results.length}>Download Results</button>
                </div>
                {summary && (
                    <div className="summary-grid">
                        <div><span>Total</span><strong>{summary.rows}</strong></div>
                        <div><span>Successful</span><strong>{summary.ok}</strong></div>
                        <div><span>Errors</span><strong>{summary.error}</strong></div>
                    </div>
                )}
                {!preview.length ? <div className="muted">No batch prediction has been run yet.</div> : (
                    <div className="table-wrap">
                        <table>
                            <thead><tr>{displayColumns.map(c => <th key={c}>{DISPLAY_HEADERS[c] || c}</th>)}</tr></thead>
                            <tbody>
                                {preview.map((row, i) => (
                                    <tr key={i}>{displayColumns.map(c => <td key={c}>{displayCell(c, row[c])}</td>)}</tr>
                                ))}
                            </tbody>
                        </table>
                        {results.length > 50 && <div className="muted table-note">Showing the first 50 rows. Download Results for the complete table.</div>}
                    </div>
                )}
            </section>
        </div>
    );
}

function App() {
    const [tab, setTab] = React.useState("single");
    const [models, setModels] = React.useState(FALLBACK_MODELS);

    React.useEffect(() => {
        fetch(`${apiBase()}/meta`)
            .then(response => response.ok ? response.json() : Promise.reject())
            .then(data => {
                if (data.models && data.models.length) setModels(data.models);
            })
            .catch(() => {});
    }, []);

    return (
        <main className="page">
            <header className="hero">
                <div>
                    <h1>CrossAS <span>V1.0</span></h1>
                    <p>Cross-species allele-specific variant prediction using fine-tuned genomic language models.</p>
                </div>
            </header>
            <nav className="tabs" aria-label="Prediction mode">
                <button className={tab === "single" ? "active" : ""} onClick={() => setTab("single")}>Single Variant Prediction</button>
                <button className={tab === "batch" ? "active" : ""} onClick={() => setTab("batch")}>Batch Variant Prediction</button>
            </nav>
            {tab === "single"
                ? <SingleVariantPrediction models={models}/>
                : <BatchVariantPrediction models={models}/>
            }
        </main>
    );
}

const root = ReactDOM.createRoot(document.getElementById("app"));
root.render(<App/>);
