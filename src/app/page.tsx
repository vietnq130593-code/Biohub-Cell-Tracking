import { SiteHeader } from "@/components/competition/site-header";
import { Hero } from "@/components/competition/hero";
import TrackingDemo from "@/components/competition/tracking-demo";
import SubmissionLab from "@/components/competition/submission-lab";
import { ContentTabs } from "@/components/competition/content-tabs";
import { GettingStarted } from "@/components/competition/getting-started";
import { FlaskConical, Dna, ExternalLink, Ruler } from "lucide-react";
import { Button } from "@/components/ui/button";
import { COMPETITION_URL } from "@/lib/competition-data";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <SiteHeader />

      <main className="flex-1">
        <Hero />

        {/* Trình mô phỏng & chấm điểm — trái tim của giao diện bài thi */}
        <section
          id="demo"
          className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-14 sm:px-6 sm:py-20"
          aria-labelledby="demo-heading"
        >
          <div className="mb-8 flex flex-col items-center text-center">
            <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
              <FlaskConical className="h-3.5 w-3.5" aria-hidden />
              Trải nghiệm tương tác
            </span>
            <h2
              id="demo-heading"
              className="text-2xl font-extrabold tracking-tight sm:text-3xl"
            >
              Tự tay &quot;chấm&quot; một bài nộp
            </h2>
            <p className="mt-2 max-w-3xl text-balance text-sm leading-relaxed text-muted-foreground sm:text-base">
              Bản mô phỏng dưới đây tái hiện một mẫu dữ liệu cuộc thi: lớp{" "}
              <strong className="text-foreground">ground-truth</strong> (đốm
              emerald — &quot;đáp án&quot;) đối chiếu với lớp{" "}
              <strong className="text-foreground">dự đoán</strong> (vòng teal)
              do <strong className="text-foreground">chính thuật toán nộp bài</strong>{" "}
              (port JS trung thành từ notebook Kaggle) chạy trên thể tích 3D tổng
              hợp. Hệ thống tự ghép node tối ưu trong ngưỡng 7.0 µm, đếm cạnh{" "}
              <strong className="text-foreground">TP/FP/FN</strong>, phát hiện{" "}
              <strong className="text-foreground">phân bào</strong> và tính điểm
              đúng công thức{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">
                adj_edge + 0.1 × division
              </code>
              . Hãy đổi giữa Ver 7 (đang chấm — port 0.947) ↔ Ver 6 (Kaggle
              0.945) — hoặc chỉnh tham số ở chế độ Tùy chỉnh — để xem điểm thay
              đổi tức thì!
            </p>
          </div>
          <TrackingDemo />
        </section>

        {/* Phòng đo lường & quy chuẩn — registry phiên bản + paired A/B */}
        <section
          id="lab"
          className="mx-auto w-full max-w-7xl scroll-mt-24 px-4 py-14 sm:px-6 sm:py-20"
          aria-labelledby="lab-heading"
        >
          <div className="mb-8 flex flex-col items-center text-center">
            <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-teal-500/30 bg-teal-500/10 px-3 py-1 text-xs font-semibold text-teal-700 dark:text-teal-300">
              <Ruler className="h-3.5 w-3.5" aria-hidden />
              Đo đạc · quy chuẩn · chẩn đoán
            </span>
            <h2
              id="lab-heading"
              className="text-2xl font-extrabold tracking-tight sm:text-3xl"
            >
              Phòng đo lường &amp; quy chuẩn
            </h2>
            <p className="mt-2 max-w-3xl text-balance text-sm leading-relaxed text-muted-foreground sm:text-base">
              Sau khi ver-6 chốt <strong className="text-foreground">0.945</strong>{" "}
              public LB (deterministic × 2 bản) và ver-7 đang được chấm, mọi
              cải tiến phải được đo trước khi tốn quota submit: registry phiên
              bản + paired A/B, máy tính điểm what-if và trình kiểm tra
              submission.csv — cả ba chạy hoàn toàn trong trình duyệt.
            </p>
          </div>
          <SubmissionLab />
        </section>

        <div className="border-t bg-muted/30">
          <ContentTabs />
        </div>

        <div className="border-t bg-gradient-to-b from-transparent to-emerald-500/[0.05]">
          <GettingStarted />
        </div>
      </main>

      <footer className="mt-auto border-t bg-[#04120c] text-white/70">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-4 py-8 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-emerald-950">
              <Dna className="h-4.5 w-4.5" aria-hidden />
            </span>
            <span className="text-sm font-semibold text-white">
              Biohub · Cell Tracking During Development
            </span>
          </div>
          <p className="max-w-2xl text-center text-xs leading-relaxed">
            Trang cẩm nang phi chính thức tổng hợp từ thông tin công khai của
            cuộc thi trên Kaggle (do Chan Zuckerberg Biohub tổ chức). Không
            liên kết chính thức với Kaggle hay Biohub. Hãy luôn kiểm tra trang
            cuộc thi chính thức để có thông tin mới nhất.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button
              asChild
              variant="secondary"
              size="sm"
              className="gap-1.5 bg-white/10 text-white hover:bg-white/20"
            >
              <a
                href={COMPETITION_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                Mở cuộc thi trên Kaggle
                <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            </Button>
            <Button
              asChild
              variant="secondary"
              size="sm"
              className="gap-1.5 bg-white/10 text-white hover:bg-white/20"
            >
              <a
                href={`${COMPETITION_URL}/rules`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Quy tắc đầy đủ
                <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            </Button>
          </div>
          <p className="text-[11px] text-white/40">
            © 2026 · Biohub Cell Tracking · Môi trường mô phỏng nội bộ các phiên
            bản pipeline
          </p>
        </div>
      </footer>
    </div>
  );
}
