import Link from "next/link";
import { ArrowRight, CheckCircle2, FlaskConical, PackageCheck, Search, Smartphone, Sparkles, Wrench } from "lucide-react";
import { Badge, Card, PageHeader } from "@/components/ui";

const steps = [
  { title: "Ý tưởng", body: "Bạn nhập ý tưởng hoặc chọn tự tìm trend. ForgeTrend biến nó thành brief rõ mục tiêu.", icon: Sparkles },
  { title: "Nghiên cứu", body: "Hệ thống lấy evidence deterministic hoặc web allowlist, rồi ghi lại finding để bạn kiểm tra.", icon: Search },
  { title: "Chọn hướng tốt nhất", body: "Các app ứng viên được chấm theo demand, pain, feasibility, originality và policy risk.", icon: CheckCircle2 },
  { title: "Tạo bản thiết kế app", body: "Autopilot tạo PRD, screen flow, blueprint, store positioning và skill context cần dùng.", icon: Smartphone },
  { title: "Code Flutter", body: "Worker tạo source Flutter local-first, có onboarding, home, core flow, settings và privacy.", icon: Wrench },
  { title: "Test và sửa lỗi", body: "ForgeTrend chạy pub get, analyze, test, debug APK. Nếu lỗi, nó tự sửa trong giới hạn an toàn.", icon: FlaskConical },
  { title: "Kiểm tra chất lượng", body: "Policy gate và quality gate chặn app generic, thiếu privacy, thiếu tính năng hoặc rủi ro store.", icon: CheckCircle2 },
  { title: "Xuất kết quả", body: "Bạn nhận APK/source/report/store assets/gói test nội bộ. Không có auto-publish.", icon: PackageCheck },
];

export default function HowItWorksPage() {
  return (
    <>
      <PageHeader
        title="ForgeTrend hoạt động thế nào?"
        description="Luồng đơn giản: nhập mục tiêu, bấm chạy, xem app ứng viên và báo cáo tiếng Việt. Log kỹ thuật chỉ là phần phụ."
        action={<Link className="inline-flex min-h-10 items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground" href="/create">Tạo app ngay <ArrowRight size={16} /></Link>}
      />

      <div className="mb-6 rounded-lg border border-border bg-card p-5">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge>Không sửa config thủ công</Badge>
          <Badge>Skill tự chọn</Badge>
          <Badge>Test tự động</Badge>
          <Badge>Không auto-publish</Badge>
          <Badge>Con người phê duyệt cuối</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <Card key={step.title}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <Icon size={18} />
                </div>
                <Badge>{index + 1}</Badge>
              </div>
              <h2 className="font-semibold">{step.title}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
            </Card>
          );
        })}
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-3">
        <Card>
          <h2 className="font-semibold">Config Studio</h2>
          <p className="mt-2 text-sm text-muted-foreground">Profile lưu provider, base URL, model, network, plugin và trusted project. API key luôn masked.</p>
        </Card>
        <Card>
          <h2 className="font-semibold">Skill Marketplace</h2>
          <p className="mt-2 text-sm text-muted-foreground">Autopilot chọn skill theo ngôn ngữ, monetization, category và lỗi trước đó để giảm prompt dài.</p>
        </Card>
        <Card>
          <h2 className="font-semibold">Learning Memory</h2>
          <p className="mt-2 text-sm text-muted-foreground">Sau mỗi run, hệ thống ghi lại lỗi, provider, archetype, skill và điểm chất lượng để lần sau chọn tốt hơn.</p>
        </Card>
      </div>
    </>
  );
}
