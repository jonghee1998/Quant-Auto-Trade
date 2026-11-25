export const metadata = { title: 'Quant Auto Trade', description: '개인용 시장 현황·뉴스·전략 검증 앱' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
