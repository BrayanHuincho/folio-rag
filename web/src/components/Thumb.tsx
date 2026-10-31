import { useEffect, useRef, useState } from "react";
import { isImage, isPdf, pdfThumbnail } from "../thumbs";

const tileColors: Record<string, string> = {
  pdf: "#e2574c",
  doc: "#2b7cd3",
  docx: "#2b7cd3",
  xls: "#1f9d55",
  xlsx: "#1f9d55",
  xlsm: "#1f9d55",
  csv: "#1f9d55",
  tsv: "#1f9d55",
  ppt: "#d24726",
  pptx: "#d24726",
};

export const tileColor = (ext: string) => tileColors[ext] ?? "#52525b";

export function TypeTile({ ext, large }: { ext: string; large?: boolean }) {
  return (
    <span className="type-tile" data-large={large || undefined} style={{ background: tileColor(ext) }}>
      {ext.slice(0, 4) || "?"}
    </span>
  );
}

interface Props {
  ext: string;
  file?: File;
  url?: string;
}

// miniatura real para PDF e imágenes; el resto usa el bloque de color del tipo
export default function Thumb({ ext, file, url }: Props) {
  const box = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(!!file);
  const [src, setSrc] = useState<string | null>(null);
  const previewable = isPdf(ext) || isImage(ext);

  useEffect(() => {
    if (visible || !previewable || !box.current) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setVisible(true), { rootMargin: "200px" });
    io.observe(box.current);
    return () => io.disconnect();
  }, [visible, previewable]);

  useEffect(() => {
    if (!visible || !previewable) return;
    const source = file ?? url;
    if (!source) return;
    if (isImage(ext)) {
      if (typeof source === "string") return setSrc(source);
      const objectUrl = URL.createObjectURL(source);
      setSrc(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    }
    let live = true;
    pdfThumbnail(source)
      .then((d) => live && setSrc(d))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [visible, previewable, ext, file, url]);

  return (
    <span className="thumb" ref={box} data-kind={src ? "image" : "tile"}>
      {src ? <img src={src} alt="" draggable={false} /> : <TypeTile ext={ext} large />}
    </span>
  );
}
