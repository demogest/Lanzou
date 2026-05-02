import { Button, EmptyState, ModalForm } from "./ui.jsx";

function HistoryItem({ active, item, onSelect }) {
  return (
    <Button className={`history-item ${active ? "active" : ""}`} variant="plain" onClick={onSelect}>
      <strong>{item.time || "-"}</strong>
      <span>
        {item.downloadedCount || 0} 个文件 · 进程 {item.processCount || 1}
      </span>
    </Button>
  );
}

function HistoryList({ history, selectedIndex, onSelect }) {
  if (!history.length) {
    return <EmptyState>暂无下载历史</EmptyState>;
  }

  return history.map((item, index) => (
    <HistoryItem
      active={index === selectedIndex}
      item={item}
      key={`${item.time || "history"}-${index}`}
      onSelect={() => onSelect(index)}
    />
  ));
}

export default function HistoryDialog({
  details,
  history,
  open,
  selectedIndex,
  onClear,
  onClose,
  onDelete,
  onSelect,
}) {
  const isEmpty = history.length === 0;

  return (
    <ModalForm bodyClassName="history-layout" className="dialog history-dialog" open={open} title="下载历史" onClose={onClose}>
      <div className="history-list-wrap">
        <div id="historyList" className="history-list">
          <HistoryList history={history} selectedIndex={selectedIndex} onSelect={onSelect} />
        </div>
        <div className="history-actions">
          <Button id="deleteHistoryBtn" disabled={isEmpty} onClick={onDelete}>
            删除选中
          </Button>
          <Button id="clearHistoryBtn" disabled={isEmpty} variant="danger" onClick={onClear}>
            清空历史
          </Button>
        </div>
      </div>
      <pre id="historyDetails" className="history-details">
        {details}
      </pre>
    </ModalForm>
  );
}
