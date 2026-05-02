import { useEffect, useRef } from "react";
import { Button, Panel, SectionHeading } from "./ui.jsx";

function LogRow({ log }) {
  return (
    <div className="log-row">
      <span>{log.type}</span>
      <span>{log.seq}</span>
      <span>{log.message}</span>
    </div>
  );
}

export default function LogPanel({ logs, onClear }) {
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [logs]);

  return (
    <Panel className="log-panel">
      <SectionHeading
        action={
          <Button className="ghost" id="clearLogBtn" variant="plain" onClick={onClear}>
            清空
          </Button>
        }
        compact
        title="下载日志"
      />
      <div className="log-table">
        <div className="log-row log-head">
          <span>阶段</span>
          <span>序号</span>
          <span>消息</span>
        </div>
        <div id="logRows">
          {logs.map((log) => (
            <LogRow key={log.id} log={log} />
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </Panel>
  );
}
