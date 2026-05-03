"use client";

import { useEffect, useState } from "react";
import { en } from "@/lib/translations/en";
import { vi } from "@/lib/translations/vi";

export type Language = "vi" | "en";

const dictionaries = { vi, en };
const storageKey = "forge-language";
const languageEvent = "forge-language-change";

export function getInitialLanguage(): Language {
  if (typeof window === "undefined") return "vi";
  const stored = window.localStorage.getItem(storageKey);
  return stored === "en" || stored === "vi" ? stored : "vi";
}

export function useLanguage() {
  const [language, setLanguageState] = useState<Language>(() => getInitialLanguage());

  useEffect(() => {
    const onChange = () => setLanguageState(getInitialLanguage());
    window.addEventListener(languageEvent, onChange);
    return () => window.removeEventListener(languageEvent, onChange);
  }, []);

  function setLanguage(language: Language) {
    window.localStorage.setItem(storageKey, language);
    setLanguageState(language);
    window.dispatchEvent(new Event(languageEvent));
  }

  function t(key: keyof typeof vi): string {
    return dictionaries[language][key] ?? dictionaries.vi[key] ?? String(key);
  }

  return { language, setLanguage, t };
}
