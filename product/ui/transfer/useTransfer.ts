import { useEffect, useState } from 'react'
import { ApiError, request } from '../shared/api.js'
import {
  failure,
  type Category,
  type Preview,
  type Rule,
  type TransferRequest,
  type Uploaded,
} from './model.js'
const defaultApi: TransferRequest = (body) => request('transfer', body)
const recoveryKey = 'huohuo-transfer-pending-preview'
export function useTransfer(api: TransferRequest = defaultApi) {
  const [uploads, setUploads] = useState<Uploaded[]>([]),
    [upload, setUpload] = useState<Uploaded>()
  const [selected, setSelected] = useState<Category[]>([]),
    [rules, setRules] = useState<Partial<Record<Category, Rule>>>({})
  const [preview, setPreview] = useState<Preview>(),
    [receipt, setReceipt] = useState<any>(),
    [busy, setBusy] = useState(false)
  const [error, setError] = useState(''),
    [unknown, setUnknown] = useState(false)
  const [recovery, setRecovery] = useState(() => sessionStorage.getItem(recoveryKey))
  async function refresh() {
    const value = await api({ operation: 'uploads' })
    setUploads(value.items)
  }
  async function check(id = preview?.preview_id ?? recovery) {
    if (!id) return
    setBusy(true)
    setError('')
    try {
      const value = await api({ operation: 'status', preview_id: id })
      setPreview(value)
      setReceipt(value.receipt)
      setUnknown(false)
      setRecovery(id)
      sessionStorage.setItem(recoveryKey, id)
    } catch (e) {
      setError(failure(e))
      if (e instanceof ApiError && e.status === 404) {
        setRecovery(null)
        setPreview(undefined)
        setReceipt(undefined)
        setUnknown(false)
        sessionStorage.removeItem(recoveryKey)
      } else setUnknown(true)
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => {
    let live = true
    api({ operation: 'uploads' })
      .then((x) => {
        if (live) setUploads(x.items)
      })
      .catch((e) => {
        if (live) setError(failure(e))
      })
    if (recovery) void check(recovery)
    return () => {
      live = false
    }
  }, [])
  function choose(value: Uploaded) {
    setUpload(value)
    setSelected(value.categories.map((x) => x.id))
    setRules({})
    setError('')
    setReceipt(undefined)
  }
  async function file(value?: File) {
    if (!value) return
    setBusy(true)
    setError('')
    try {
      if (!value.name.toLowerCase().endsWith('.json') || value.size > 20 * 1024 * 1024)
        throw Error('请选择不超过 20 MiB 的 JSON 文件。')
      const result = await api({
        operation: 'upload',
        request_key: crypto.randomUUID(),
        filename: value.name,
        content: await value.text(),
      })
      choose(result)
      await refresh()
    } catch (e) {
      setError(failure(e))
    } finally {
      setBusy(false)
    }
  }
  async function prepare() {
    if (!upload) return
    setBusy(true)
    setError('')
    try {
      const result = await api({
        operation: 'prepare',
        upload_id: upload.upload_id,
        request_key: crypto.randomUUID(),
        selected,
        rules: Object.fromEntries(selected.map((x) => [x, rules[x] ?? 'keep_local'])),
      })
      setPreview(result)
      setRecovery(result.preview_id)
      sessionStorage.setItem(recoveryKey, result.preview_id)
    } catch (e) {
      setError(failure(e))
    } finally {
      setBusy(false)
    }
  }
  async function commit() {
    if (!preview?.can_commit || unknown) return
    setBusy(true)
    setError('')
    try {
      setReceipt(
        await api({
          operation: 'commit',
          preview_id: preview.preview_id,
          request_key: preview.request_key,
        }),
      )
      setUnknown(false)
    } catch (e) {
      setError(`${failure(e)} 请先核对回执，避免重复导入。`)
      setUnknown(true)
    } finally {
      setBusy(false)
    }
  }
  async function back() {
    if (preview && !receipt) {
      setBusy(true)
      setError('')
      try {
        await api({ operation: 'cancel', preview_id: preview.preview_id })
      } catch (e) {
        setError(failure(e))
        setUnknown(true)
        setBusy(false)
        return
      }
      setBusy(false)
    }
    setPreview(undefined)
    setReceipt(undefined)
    setRecovery(null)
    setUnknown(false)
    sessionStorage.removeItem(recoveryKey)
  }
  async function remove(id: string) {
    setBusy(true)
    setError('')
    try {
      await api({ operation: 'remove_upload', upload_id: id })
      if (upload?.upload_id === id) setUpload(undefined)
      await refresh()
    } catch (e) {
      setError(failure(e))
    } finally {
      setBusy(false)
    }
  }
  const locked = busy || !!preview || unknown
  return {
    api,
    uploads,
    upload,
    selected,
    setSelected,
    rules,
    setRules,
    preview,
    receipt,
    busy,
    error,
    unknown,
    locked,
    check,
    choose,
    file,
    prepare,
    commit,
    back,
    remove,
  }
}
