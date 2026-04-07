import { useEffect } from "react";

const tg = window.Telegram?.WebApp;

export function useTelegram() {
  useEffect(() => {
    tg?.ready();
  }, []);

  return {
    tg,
    user: tg?.initDataUnsafe?.user,
    initData: tg?.initData ?? "",
    themeParams: tg?.themeParams ?? {},
    close: () => tg?.close(),
    MainButton: tg?.MainButton,
    BackButton: tg?.BackButton,
  };
}
