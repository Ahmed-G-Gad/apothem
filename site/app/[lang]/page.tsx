// SPDX-License-Identifier: MIT

import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowRight, BookOpen } from 'lucide-react';
import type { Metadata } from 'next';
import pkg from '@/package.json';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AnimatedMark } from '@/components/animated-mark';
import { LandingNav } from '@/components/landing-nav';
import { LandingFooter } from '@/components/landing-footer';
import { buildAlternates } from '@/lib/hreflang';
import {
  ROUTED_NON_DEFAULT_LOCALES,
  COHORT_LOCALES,
} from '@/lib/i18n';

// Localized landing surface for non-default routed locales. The rich English
// landing page (app/page.tsx) is a bespoke marketing surface; each locale gets
// a concise localized entry card that routes into that locale's documentation.

// Concise per-locale landing copy. Keyed by the routed URL-path segment (the
// `[lang]` route param), which for code≠path locales differs from the BCP-47
// code (e.g. path `zh-cn` vs. code `zh-CN`). The short strings are
// locale-authored here, reusing the translated product description from each
// locale's `content/docs/<locale>/index.mdx`. Every routed non-default
// locale carries an entry; missing entries fall through to `notFound()`.
const LANDING_COPY: Record<
  string,
  {
    badge: string;
    tagline: string;
    lede: string;
    readDocs: string;
    quickStart: string;
  }
> = {
  es: {
    badge: 'Un perfil · diecisiete entornos',
    tagline: 'Un perfil, cada entorno.',
    lede: 'Defines un único perfil compartido y Apothem lo materializa en la configuración nativa de diecisiete entornos: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed y el resto del catálogo registrado.',
    readDocs: 'Leer la documentación',
    quickStart: 'Guía rápida',
  },
  'zh-cn': {
    badge: '一份配置档案 · 十七个环境',
    tagline: '一份配置档案，适配每个环境。',
    lede: '你编写一份共享配置档案，Apothem 会将其物化为十七个环境的原生配置面——Claude Code、Cursor、Gemini CLI、GitHub Copilot、Codex、Windsurf、Zed，以及已注册目录中的其余工具。',
    readDocs: '阅读文档',
    quickStart: '快速开始',
  },
  'pt-br': {
    badge: 'Um perfil · dezessete ambientes',
    tagline: 'Um perfil, cada ambiente.',
    lede: 'Você escreve um único perfil compartilhado e o Apothem o materializa na configuração nativa de dezessete ambientes: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed e o restante do catálogo registrado.',
    readDocs: 'Ler a documentação',
    quickStart: 'Guia rápido',
  },
  fr: {
    badge: 'Un profil · dix-sept environnements',
    tagline: 'Un profil, chaque environnement.',
    lede: "Vous rédigez un seul profil partagé et Apothem le matérialise dans la configuration native de dix-sept environnements : Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed et le reste du catalogue enregistré.",
    readDocs: 'Lire la documentation',
    quickStart: 'Démarrage rapide',
  },
  de: {
    badge: 'Ein Profil · siebzehn Umgebungen',
    tagline: 'Ein Profil, jede Umgebung.',
    lede: 'Du schreibst ein einziges gemeinsames Profil, und Apothem materialisiert es in die native Konfiguration von siebzehn Umgebungen: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed und den Rest des registrierten Katalogs.',
    readDocs: 'Dokumentation lesen',
    quickStart: 'Schnellstart',
  },
  ja: {
    badge: '1 つのプロファイル · 17 の環境',
    tagline: '1 つのプロファイルで、あらゆる環境へ。',
    lede: '1 つの共有プロファイルを記述すると、Apothem はそれを 17 の環境のネイティブ設定へ物化します——Claude Code、Cursor、Gemini CLI、GitHub Copilot、Codex、Windsurf、Zed、そして登録済みカタログのその他のツールです。',
    readDocs: 'ドキュメントを読む',
    quickStart: 'クイックスタート',
  },
  ko: {
    badge: '하나의 프로파일 · 열일곱 개 환경',
    tagline: '하나의 프로파일로, 모든 환경에.',
    lede: '하나의 공유 프로파일을 작성하면 Apothem이 이를 열일곱 개 환경의 네이티브 설정으로 물화합니다 — Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed, 그리고 등록된 카탈로그의 나머지 도구들입니다.',
    readDocs: '문서 읽기',
    quickStart: '빠른 시작',
  },
  ru: {
    badge: 'Один профиль · семнадцать сред',
    tagline: 'Один профиль — каждая среда.',
    lede: 'Вы описываете один общий профиль, и Apothem материализует его в нативную конфигурацию семнадцати сред: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed и остальных инструментов зарегистрированного каталога.',
    readDocs: 'Читать документацию',
    quickStart: 'Быстрый старт',
  },
  id: {
    badge: 'Satu profil · tujuh belas lingkungan',
    tagline: 'Satu profil, setiap lingkungan.',
    lede: 'Anda menulis satu profil bersama, dan Apothem mematerialisasikannya ke konfigurasi native tujuh belas lingkungan: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed, dan sisa katalog yang terdaftar.',
    readDocs: 'Baca dokumentasi',
    quickStart: 'Mulai cepat',
  },
  hi: {
    badge: 'एक प्रोफ़ाइल · सत्रह हार्नेस',
    tagline: 'एक प्रोफ़ाइल, हर हार्नेस।',
    lede: 'आप एक साझा प्रोफ़ाइल लिखते हैं, और Apothem उसे सत्रह हार्नेस के नेटिव कॉन्फ़िगरेशन में मूर्त रूप देता है: Claude Code, Cursor, Gemini CLI, GitHub Copilot, Codex, Windsurf, Zed, और पंजीकृत कैटलॉग के शेष टूल।',
    readDocs: 'दस्तावेज़ पढ़ें',
    quickStart: 'त्वरित आरंभ',
  },
  ar: {
    badge: 'ملف تعريف واحد · سبع عشرة بيئة',
    tagline: 'ملف تعريف واحد، لكل بيئة.',
    lede: 'تكتب ملف تعريف مشترك واحد، فيحوِّله Apothem إلى التهيئة الأصلية لسبع عشرة بيئة: Claude Code وCursor وGemini CLI وGitHub Copilot وCodex وWindsurf وZed، وبقية الأدوات في الكتالوج المُسجَّل.',
    readDocs: 'اقرأ الوثائق',
    quickStart: 'البدء السريع',
  },
};

export function generateStaticParams() {
  return ROUTED_NON_DEFAULT_LOCALES.map((lang) => ({ lang }));
}

export async function generateMetadata(props: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await props.params;
  const copy = LANDING_COPY[lang];
  if (!copy) notFound();
  return {
    title: 'Apothem',
    description: copy.tagline,
    alternates: buildAlternates(`/${lang}`),
  };
}

export default async function LocaleHome(props: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await props.params;
  const copy = LANDING_COPY[lang];
  // `lang` is the routed URL-path segment (e.g. `zh-cn`, `pt-br`), which for
  // code≠path locales differs from the BCP-47 code (`zh-CN`, `pt-BR`); match on
  // `path`, not `code`, so those locales resolve instead of 404-ing.
  const locale = COHORT_LOCALES.find((l) => l.path === lang);
  if (!copy || !locale) notFound();

  return (
    <div className="flex min-h-screen flex-col">
      <LandingNav localePrefix={`/${lang}`} />
      <main
        id="main-content"
        dir={locale.dir}
        className="relative flex flex-1 items-center overflow-hidden"
      >
      <div
        aria-hidden
        className="apothem-grid pointer-events-none absolute inset-0"
      />
      <div className="relative mx-auto flex max-w-3xl flex-col items-center gap-8 px-4 py-24 text-center sm:px-6 sm:py-32">
        <div className="relative flex items-center justify-center">
          <div
            aria-hidden
            className="apothem-glow pointer-events-none absolute -inset-16 -z-10"
          />
          <AnimatedMark size={120} className="drop-shadow-sm" />
        </div>

        <div className="flex flex-col items-center gap-5">
          <Badge variant="accent" className="font-mono">
            {copy.badge}
          </Badge>
          <h1 className="text-balance text-5xl font-bold tracking-tight sm:text-6xl">
            Apothem
          </h1>
          <p className="max-w-2xl text-balance text-lg text-fd-muted-foreground sm:text-xl">
            {copy.tagline}
          </p>
          <p className="max-w-2xl text-balance text-base text-fd-muted-foreground">
            {copy.lede}
          </p>
        </div>

        <div className="flex flex-col items-center gap-3 sm:flex-row">
          <Button asChild size="lg">
            <Link href={`/${lang}/docs`}>
              <BookOpen className="size-4" />
              {copy.readDocs}
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href={`/${lang}/docs/install/quickstart`}>
              {copy.quickStart}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>

        </div>
      </main>
      <LandingFooter version={pkg.version} localePrefix={`/${lang}`} />
    </div>
  );
}
