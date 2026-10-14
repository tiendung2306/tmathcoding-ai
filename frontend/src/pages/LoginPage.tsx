import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { login } from '../services/auth';
import { loginErrorMessage } from '../lib/authErrors';

export function LoginPage() {
  const [params] = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { document.title = 'Đăng nhập · tmath'; }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username, password);
      const next = params.get('next');
      const target = next?.startsWith('/') && !next.startsWith('//') ? new URL(next, window.location.origin) : null;
      const safeNext = target?.origin === window.location.origin ? `${target.pathname}${target.search}${target.hash}` : '/student/students';
      window.location.assign(safeNext);
    } catch (cause) {
      setError(loginErrorMessage(cause));
      setBusy(false);
    }
  };

  return <main className="grid min-h-screen place-items-center bg-app px-4 py-8">
    <div className="w-full max-w-sm">
      <div className="mx-auto mb-6 flex min-h-11 w-fit items-center gap-2.5 text-lg font-semibold text-text-primary">
        <img src="/tmath-logo.png" alt="" className="h-9 w-9 object-contain" />
        <span>tmath</span>
      </div>
      <Card className="shadow-xs" role="region" aria-labelledby="login-title">
        <CardHeader className="border-b-0 px-6 pb-0 pt-6">
          <h1 id="login-title" className="text-xl font-semibold tracking-tight">Đăng nhập</h1>
          <CardDescription className="text-sm">Nhập tài khoản admin để xem danh sách lớp.</CardDescription>
        </CardHeader>
        <CardContent className="px-6 pb-6 pt-6">
          <form onSubmit={submit} className="grid gap-4">
            {params.get('reason') === 'session-expired' && <p role="status" className="text-sm text-text-secondary">Phiên đăng nhập đã kết thúc. Vui lòng đăng nhập lại.</p>}
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="username">Tên tài khoản</label>
              <Input id="username" name="username" autoComplete="username" required autoFocus minLength={3} maxLength={64}
                value={username} onChange={event => setUsername(event.target.value)} className="h-11 text-sm" />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="password">Mật khẩu</label>
              <Input id="password" name="password" type="password" autoComplete="current-password" required maxLength={1024}
                value={password} onChange={event => setPassword(event.target.value)} className="h-11 text-sm" />
            </div>
            {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
            <Button type="submit" size="lg" disabled={busy} className="mt-1 h-11 w-full text-sm">{busy ? 'Đang đăng nhập...' : 'Đăng nhập'}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </main>;
}
