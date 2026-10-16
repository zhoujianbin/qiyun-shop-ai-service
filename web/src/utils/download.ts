import dayjs from 'dayjs';

/** 浏览器端导出 CSV（文件名带时间戳），数据由页面提供的行生成。 */
export function downloadCsv(filenamePrefix: string, headers: string[], rows: Array<Array<string | number>>): void {
  const escape = (cell: string | number) => {
    const text = String(cell ?? '');
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const csv = [headers.map(escape).join(','), ...rows.map((row) => row.map(escape).join(','))].join('\n');
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${filenamePrefix}_${dayjs().format('YYYYMMDD_HHmmss')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}
