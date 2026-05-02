import { Button, ModalForm } from "./ui.jsx";

export default function CompleteDialog({ open, text, onClose, onOpenFolder }) {
  return (
    <ModalForm
      className="dialog small-dialog"
      footer={
        <>
          <Button type="submit" value="cancel">
            关闭
          </Button>
          <Button id="openFolderBtn" variant="primary" onClick={onOpenFolder}>
            打开文件夹
          </Button>
        </>
      }
      open={open}
      title="下载完成"
      onClose={onClose}
    >
      <p id="completeText">{text}</p>
    </ModalForm>
  );
}
