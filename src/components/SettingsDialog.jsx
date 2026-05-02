import { Button, Field, InlineField, ModalForm, TextInput } from "./ui.jsx";

export default function SettingsDialog({
  form,
  maxProcesses,
  open,
  onChange,
  onChooseDirectory,
  onClose,
  onSave,
}) {
  const updateForm = (field, value) => onChange({ ...form, [field]: value });

  return (
    <ModalForm
      bodyClassName="dialog-body"
      footer={
        <>
          <Button type="submit" value="cancel">
            取消
          </Button>
          <Button id="saveSettingsBtn" variant="primary" onClick={onSave}>
            保存
          </Button>
        </>
      }
      open={open}
      title="下载设置"
      onClose={onClose}
    >
      <Field id="defaultDir" label="默认目录">
        <InlineField>
          <TextInput
            id="defaultDir"
            value={form.defaultDownloadDir}
            onChange={(event) => updateForm("defaultDownloadDir", event.target.value)}
          />
          <Button id="chooseDefaultDirBtn" onClick={onChooseDirectory}>
            选择目录
          </Button>
        </InlineField>
      </Field>

      <Field id="processCount" label="下载进程">
        <TextInput
          id="processCount"
          max={maxProcesses}
          min="1"
          step="1"
          type="number"
          value={form.processCount}
          onChange={(event) => updateForm("processCount", event.target.value)}
        />
      </Field>
    </ModalForm>
  );
}
