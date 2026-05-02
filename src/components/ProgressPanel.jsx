import { MiniProgress, Panel, ProgressBar, SectionHeading } from "./ui.jsx";

function ProcessRow({ row }) {
  const fileName = row.fileName || "等待任务";

  return (
    <div className="process-row" data-slot={row.slot}>
      <span className="slot">进程 {row.slot}</span>
      <span className="file" title={row.fileName || ""}>
        {fileName}
      </span>
      <MiniProgress value={row.progress} />
      <span className="process-status">{row.status || "下载中"}</span>
    </div>
  );
}

export default function ProgressPanel({ processRows, statusText, totalProgress }) {
  return (
    <Panel className="progress-panel">
      <SectionHeading metric={`${totalProgress}%`} subtitle={statusText} title="任务进度" />
      <ProgressBar id="totalProgress" label="总进度" value={totalProgress} />
      <div id="processList" className="process-list">
        {processRows.map((row) => (
          <ProcessRow key={row.slot} row={row} />
        ))}
      </div>
    </Panel>
  );
}
