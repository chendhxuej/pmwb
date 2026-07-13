import dayjs from 'dayjs'

export function formatDate(date, format = 'YYYY-MM-DD') {
  if (!date) return '-'
  return dayjs(date).format(format)
}

export function formatDateTime(date) {
  return formatDate(date, 'YYYY-MM-DD HH:mm:ss')
}

export function getStatusOptions(statusMap) {
  return Object.entries(statusMap).map(([value, item]) => ({
    value,
    label: typeof item === 'string' ? item : item.label,
    type: typeof item === 'object' ? item.type : '',
  }))
}
