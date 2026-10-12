import axios from 'axios';

export function loginErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Không thể đăng nhập. Hãy thử lại.';
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
    return 'Máy chủ phản hồi quá lâu. Hãy thử lại.';
  }
  if (!error.response) return 'Không thể kết nối đến máy chủ. Kiểm tra kết nối mạng và thử lại.';
  const { status, headers } = error.response;
  if (status === 401) return 'Tên tài khoản hoặc mật khẩu không đúng.';
  if (status === 403) return 'Yêu cầu đăng nhập bị từ chối. Hãy tải lại trang và thử lại.';
  if (status === 400 || status === 422) return 'Thông tin đăng nhập không hợp lệ. Hãy kiểm tra lại.';
  if (status === 429) {
    const seconds = Number(headers['retry-after']);
    return Number.isFinite(seconds) && seconds > 0
      ? `Bạn đã thử quá nhiều lần. Hãy thử lại sau ${Math.ceil(seconds)} giây.`
      : 'Bạn đã thử quá nhiều lần. Hãy đợi 15 phút.';
  }
  if (status >= 500) return 'Đăng nhập tạm thời không khả dụng. Hãy thử lại sau.';
  return 'Không thể đăng nhập. Hãy thử lại.';
}
