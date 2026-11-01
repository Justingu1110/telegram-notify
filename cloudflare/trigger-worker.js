export default {
  async scheduled(event, env, ctx) {
    const res = await fetch(
      "https://api.github.com/repos/Justingu1110/telegram-notify/actions/workflows/check.yml/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "telegram-notify-trigger",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );
    if (res.status !== 204) {
      throw new Error(`GitHub answered ${res.status}`);
    }
  },
};
