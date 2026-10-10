import React from 'react';

export function SettingsPage() {
  return <section className="mx-auto max-w-3xl p-4 sm:p-6 lg:p-8" aria-labelledby="settings-title">
    <div className="border border-border bg-card p-5 sm:p-6 rounded-lg">
      <h1 id="settings-title" className="text-xl font-semibold text-text-primary">Cài đặt</h1>
      <p className="mt-2 max-w-xl text-sm leading-6 text-text-secondary">
        Khu vực này sẽ hiển thị các tùy chọn cá nhân sau khi tính năng đăng nhập được bổ sung.
      </p>
    </div>
  </section>;
}
