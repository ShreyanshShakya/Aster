import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Aster Platform",
  description: "Distributed AI research operations platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
