// PM2 ecosystem — duy trì giao diện app Biohub Cell Tracking (Next.js, port 3000)
// Quản lý bằng: pm2 start|restart|stop|logs|status biohub-web
// Logs app ghi thẳng vào /home/z/my-project/dev.log (output + error)
module.exports = {
  apps: [
    {
      name: "biohub-web",
      script: "/home/z/my-project/scripts/pm2-start.sh",
      cwd: "/home/z/my-project",
      autorestart: true, // tự khởi động lại khi process crash
      watch: false, // Next.js dev đã có HMR riêng, không cần pm2 watch
      max_restarts: 30,
      min_uptime: "15s", // reset bộ đếm restart nếu app sống đủ 15s
      exp_backoff_restart_delay: 2000, // restart chờ 2s → 4s → 8s... tránh vòng lặp dồn dập
      kill_timeout: 5000, // SIGINT trước, chờ 5s cho next tắt worker, rồi mới SIGKILL
      output: "/home/z/my-project/dev.log",
      error: "/home/z/my-project/dev.log",
      merge_logs: true,
      env: {
        NODE_ENV: "development",
        PORT: "3000",
      },
    },
  ],
};
