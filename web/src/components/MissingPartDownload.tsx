import { useId } from "react";

export function MissingPartDownload({ url, message }: { url: string | null; message: string }) {
  const descriptionId = useId();

  return (
    <div className="panel download-panel">
      <h2>Missing part</h2>
      <p className="small-note" id={descriptionId} role="status">{message}</p>
      {url ? (
        <a className="btn primary download-stl" href={url} download aria-describedby={descriptionId}>
          Download the STL file
        </a>
      ) : (
        <button type="button" className="btn primary download-stl" disabled aria-describedby={descriptionId}>
          Download the STL file
        </button>
      )}
      {url && <p className="small-note">Missing part only · STL · millimetres. Physical fit has not been tested.</p>}
    </div>
  );
}
