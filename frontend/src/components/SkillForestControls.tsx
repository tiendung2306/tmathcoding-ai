export function Pager({ page, pages, total, onPage }: {page: number; pages: number; total: number; onPage: (page: number) => void}) {
  return <nav className="forest-pager" aria-label="Phân trang"><span>{total} kết quả · Trang {page}/{pages}</span><div>
    <button className="skill-secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>Trước</button>
    <button className="skill-secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>Sau</button>
  </div></nav>;
}

export function QueryError({ retry }: {retry: () => void}) {
  return <div className="skill-error" role="alert">Không tải được dữ liệu. <button className="skill-text-button" onClick={retry}>Thử lại</button></div>;
}
