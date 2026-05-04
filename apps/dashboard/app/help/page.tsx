"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";
import { Card, PageHeader, Notice } from "@/components/ui";

export default function HelpPage() {
  const { t } = useLanguage();
  return (
    <>
      <PageHeader title={t("helpTitle")} description={t("helpDescription")} />
      <div className="grid gap-5 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-base font-semibold">Tạo app đầu tiên</h2>
          <p className="text-sm text-muted-foreground">Vào <Link className="text-primary" href="/create">Tạo app</Link>, nhập một câu mô tả app, chọn ngôn ngữ và bấm tạo. Các tuỳ chọn kỹ thuật đã được ẩn trong phần mở rộng.</p>
        </Card>
        <Card>
          <h2 className="mb-3 text-base font-semibold">Xem kết quả</h2>
          <p className="text-sm text-muted-foreground">Vào <Link className="text-primary" href="/artifacts">Artifact</Link> để copy đường dẫn APK, source, report, store assets và gói test nội bộ.</p>
        </Card>
        <Card>
          <h2 className="mb-3 text-base font-semibold">Khi nào cần con người review?</h2>
          <p className="text-sm text-muted-foreground">Mọi app đều cần con người duyệt trước production. `release_candidate` nghĩa là đã qua gate tự động để review tiếp; `NEEDS_HUMAN_REVIEW` nghĩa là có blocker cần sửa.</p>
        </Card>
        <Card>
          <h2 className="mb-3 text-base font-semibold">Khi thiếu công cụ</h2>
          <p className="text-sm text-muted-foreground">Vào Setup để xem Docker, Flutter, Android SDK, Python, Node/pnpm và Codex. Bootstrap terminal cũng ghi log trong thư mục `logs/`.</p>
        </Card>
      </div>
      <Notice tone="neutral" className="mt-5">{t("humanApprovalRequired")}</Notice>
    </>
  );
}
