import { useState, useRef, useCallback } from "react";

const MOCK_ELEMENTS = [
  {
    label: "Enfants",
    tiab: "children OR childhood OR pediatric OR youth",
    mesh: null,
    search_filter: true,
    priority: 1,
    reason: "Population spécifique, toujours filtrer",
  },
  {
    label: "Diabète",
    tiab: "diabetes OR diabetic OR hyperglycemia OR type 2 diabetes",
    mesh: null,
    search_filter: true,
    priority: 1,
    reason: "Condition centrale de la question",
  },
  {
    label: "Mali",
    tiab: 'Mali OR "West Africa" OR "Sub-Saharan Africa"',
    mesh: null,
    search_filter: true,
    priority: 2,
    reason: "Géographie mentionnée, utile pour affiner",
  },
  {
    label: "Prévalence",
    tiab: "burden OR epidemiology OR frequency OR incidence OR prevalence",
    mesh: '"Prevalence"[MeSH] OR "Incidence"[MeSH]',
    search_filter: false,
    priority: null,
    reason: "Terme trop générique — un article pertinent pourrait ne pas le mentionner",
  },
];

const COLORS = {
  bg: "#FAFAF8",
  surface: "#FFFFFF",
  surfaceHover: "#F5F5F0",
  border: "#E8E6E1",
  borderActive: "#B8B5AD",
  text: "#1A1A18",
  textSecondary: "#6B6966",
  textMuted: "#9C9990",
  accent: "#2D5F2D",
  accentLight: "#E8F0E8",
  accentMuted: "#4A7C4A",
  warning: "#8B6914",
  warningLight: "#FDF6E3",
  warningBorder: "#E8D5A0",
  dropzone: "#F0F4F0",
  dropzoneActive: "#E0EAE0",
  excluded: "#F7F6F4",
};

const fonts = {
  display: "'Newsreader', 'Georgia', serif",
  body: "'DM Sans', 'Helvetica Neue', sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
};

function ConceptBlock({ element, isDragging, onDragStart, onDragEnd, isInQuery, onRemove }) {
  const isExcluded = !element.search_filter;
  
  return (
    <div
      draggable={!isExcluded}
      onDragStart={(e) => {
        if (isExcluded) return;
        onDragStart(e, element);
      }}
      onDragEnd={onDragEnd}
      style={{
        padding: "14px 16px",
        borderRadius: "10px",
        border: `1.5px solid ${isExcluded ? COLORS.warningBorder : isInQuery ? COLORS.accent : COLORS.border}`,
        background: isExcluded ? COLORS.warningLight : isInQuery ? COLORS.accentLight : COLORS.surface,
        cursor: isExcluded ? "default" : "grab",
        opacity: isDragging ? 0.4 : isExcluded ? 0.7 : 1,
        transition: "all 0.2s ease",
        position: "relative",
        userSelect: "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div
            style={{
              fontFamily: fonts.body,
              fontWeight: 600,
              fontSize: "14px",
              color: isExcluded ? COLORS.warning : COLORS.text,
              marginBottom: "6px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {element.label}
            {element.priority && (
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 500,
                  padding: "2px 6px",
                  borderRadius: "4px",
                  background: element.priority === 1 ? COLORS.accent : COLORS.borderActive,
                  color: "#fff",
                  letterSpacing: "0.02em",
                }}
              >
                P{element.priority}
              </span>
            )}
          </div>
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: "11px",
              color: COLORS.textSecondary,
              lineHeight: 1.5,
              wordBreak: "break-word",
            }}
          >
            {element.tiab}
          </div>
          {element.mesh && (
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: "10px",
                color: COLORS.accentMuted,
                marginTop: "4px",
                lineHeight: 1.4,
              }}
            >
              + {element.mesh.split(" OR ").length} MeSH
            </div>
          )}
        </div>
        {isInQuery && !isExcluded && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove(element);
            }}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: COLORS.textMuted,
              fontSize: "18px",
              lineHeight: 1,
              padding: "0 0 0 8px",
              fontFamily: fonts.body,
            }}
          >
            ×
          </button>
        )}
      </div>
      {isExcluded && (
        <div
          style={{
            marginTop: "8px",
            paddingTop: "8px",
            borderTop: `1px solid ${COLORS.warningBorder}`,
            fontFamily: fonts.body,
            fontSize: "11px",
            color: COLORS.warning,
            lineHeight: 1.4,
            fontStyle: "italic",
          }}
        >
          Non recommandé — {element.reason.toLowerCase()}
        </div>
      )}
    </div>
  );
}

function AndConnector() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "4px 0",
      }}
    >
      <span
        style={{
          fontFamily: fonts.mono,
          fontSize: "11px",
          fontWeight: 600,
          color: COLORS.accent,
          letterSpacing: "0.08em",
          background: COLORS.accentLight,
          padding: "2px 10px",
          borderRadius: "4px",
        }}
      >
        AND
      </span>
    </div>
  );
}

export default function QueryWorkspace() {
  const [queryElements, setQueryElements] = useState(
    MOCK_ELEMENTS.filter((e) => e.search_filter && e.priority === 1)
  );
  const [availableElements, setAvailableElements] = useState(
    MOCK_ELEMENTS.filter((e) => !e.search_filter || e.priority !== 1)
  );
  const [draggedElement, setDraggedElement] = useState(null);
  const [isDragOverQuery, setIsDragOverQuery] = useState(false);
  const [isDragOverAvailable, setIsDragOverAvailable] = useState(false);
  const [resultCount, setResultCount] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  const handleDragStart = useCallback((e, element) => {
    setDraggedElement(element);
    e.dataTransfer.effectAllowed = "move";
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggedElement(null);
    setIsDragOverQuery(false);
    setIsDragOverAvailable(false);
  }, []);

  const handleDropOnQuery = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragOverQuery(false);
      if (!draggedElement || draggedElement.search_filter === false) return;
      if (queryElements.find((el) => el.label === draggedElement.label)) return;

      setQueryElements((prev) => [...prev, draggedElement]);
      setAvailableElements((prev) => prev.filter((el) => el.label !== draggedElement.label));
      setResultCount(null);
    },
    [draggedElement, queryElements]
  );

  const handleDropOnAvailable = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragOverAvailable(false);
      if (!draggedElement) return;
      if (availableElements.find((el) => el.label === draggedElement.label)) return;

      setAvailableElements((prev) => [...prev, draggedElement]);
      setQueryElements((prev) => prev.filter((el) => el.label !== draggedElement.label));
      setResultCount(null);
    },
    [draggedElement, availableElements]
  );

  const handleRemoveFromQuery = useCallback((element) => {
    setQueryElements((prev) => prev.filter((el) => el.label !== element.label));
    setAvailableElements((prev) => [...prev, element]);
    setResultCount(null);
  }, []);

  const handleSearch = useCallback(() => {
    setIsSearching(true);
    const counts = {
      2: 48392,
      3: 84,
      4: 312,
      1: 193847,
    };
    setTimeout(() => {
      setResultCount(counts[queryElements.length] || Math.floor(Math.random() * 10000));
      setIsSearching(false);
    }, 800);
  }, [queryElements]);

  const buildQueryPreview = () => {
    return queryElements
      .map((e) => {
        const parts = [];
        if (e.mesh) parts.push(e.mesh);
        const tiabTerms = e.tiab
          .split(" OR ")
          .map((t) => (t.trim().includes(" ") ? `"${t.trim()}"[TIAB]` : `${t.trim()}[TIAB]`));
        parts.push(tiabTerms.join(" OR "));
        return `(${parts.join(" OR ")})`;
      })
      .join("\nAND ");
  };

  return (
    <div style={{ background: COLORS.bg, minHeight: "100vh", padding: "40px 20px" }}>
      <link
        href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
        rel="stylesheet"
      />

      <div style={{ maxWidth: "860px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: "48px" }}>
          <h1
            style={{
              fontFamily: fonts.display,
              fontSize: "28px",
              fontWeight: 600,
              color: COLORS.text,
              margin: "0 0 8px 0",
              letterSpacing: "-0.01em",
            }}
          >
            Construisez votre recherche
          </h1>
          <p
            style={{
              fontFamily: fonts.body,
              fontSize: "14px",
              color: COLORS.textSecondary,
              margin: 0,
              lineHeight: 1.5,
            }}
          >
            Glissez les concepts dans la zone de recherche pour composer votre requête.
            Chaque concept ajouté affine les résultats.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "32px" }}>
          {/* Left: Available concepts */}
          <div>
            <h2
              style={{
                fontFamily: fonts.body,
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: COLORS.textMuted,
                margin: "0 0 16px 0",
              }}
            >
              Concepts disponibles
            </h2>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOverAvailable(true);
              }}
              onDragLeave={() => setIsDragOverAvailable(false)}
              onDrop={handleDropOnAvailable}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "10px",
                minHeight: "120px",
                padding: "12px",
                borderRadius: "12px",
                border: `1.5px dashed ${isDragOverAvailable ? COLORS.borderActive : "transparent"}`,
                background: isDragOverAvailable ? COLORS.surfaceHover : "transparent",
                transition: "all 0.2s ease",
              }}
            >
              {availableElements.length === 0 && !MOCK_ELEMENTS.some((e) => !e.search_filter) && (
                <p
                  style={{
                    fontFamily: fonts.body,
                    fontSize: "13px",
                    color: COLORS.textMuted,
                    textAlign: "center",
                    padding: "20px 0",
                    margin: 0,
                  }}
                >
                  Tous les concepts sont dans votre requête
                </p>
              )}
              {availableElements.map((el) => (
                <ConceptBlock
                  key={el.label}
                  element={el}
                  isDragging={draggedElement?.label === el.label}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                  isInQuery={false}
                  onRemove={() => {}}
                />
              ))}
            </div>
          </div>

          {/* Right: Query zone */}
          <div>
            <h2
              style={{
                fontFamily: fonts.body,
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: COLORS.textMuted,
                margin: "0 0 16px 0",
              }}
            >
              Votre requête
            </h2>

            {/* Drop zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOverQuery(true);
              }}
              onDragLeave={() => setIsDragOverQuery(false)}
              onDrop={handleDropOnQuery}
              style={{
                minHeight: "180px",
                padding: "16px",
                borderRadius: "12px",
                border: `1.5px dashed ${isDragOverQuery ? COLORS.accent : COLORS.border}`,
                background: isDragOverQuery ? COLORS.dropzoneActive : COLORS.dropzone,
                transition: "all 0.2s ease",
              }}
            >
              {queryElements.length === 0 ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "148px",
                    fontFamily: fonts.body,
                    fontSize: "13px",
                    color: COLORS.textMuted,
                  }}
                >
                  Glissez des concepts ici pour construire votre requête
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
                  {queryElements.map((el, i) => (
                    <div key={el.label}>
                      <ConceptBlock
                        element={el}
                        isDragging={draggedElement?.label === el.label}
                        onDragStart={handleDragStart}
                        onDragEnd={handleDragEnd}
                        isInQuery={true}
                        onRemove={handleRemoveFromQuery}
                      />
                      {i < queryElements.length - 1 && <AndConnector />}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Query preview */}
            {queryElements.length > 0 && (
              <div style={{ marginTop: "20px" }}>
                <div
                  style={{
                    fontFamily: fonts.body,
                    fontSize: "11px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: COLORS.textMuted,
                    marginBottom: "8px",
                  }}
                >
                  Aperçu PubMed
                </div>
                <pre
                  style={{
                    fontFamily: fonts.mono,
                    fontSize: "11px",
                    lineHeight: 1.6,
                    color: COLORS.text,
                    background: COLORS.surface,
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: "8px",
                    padding: "14px 16px",
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    overflow: "auto",
                  }}
                >
                  {buildQueryPreview()}
                </pre>

                {/* Search button */}
                <div style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "16px" }}>
                  <button
                    onClick={handleSearch}
                    disabled={isSearching}
                    style={{
                      fontFamily: fonts.body,
                      fontSize: "13px",
                      fontWeight: 600,
                      padding: "10px 24px",
                      borderRadius: "8px",
                      border: "none",
                      background: COLORS.accent,
                      color: "#fff",
                      cursor: isSearching ? "wait" : "pointer",
                      opacity: isSearching ? 0.7 : 1,
                      transition: "all 0.15s ease",
                      letterSpacing: "0.01em",
                    }}
                  >
                    {isSearching ? "Recherche..." : "Lancer la recherche"}
                  </button>

                  {resultCount !== null && (
                    <span
                      style={{
                        fontFamily: fonts.body,
                        fontSize: "14px",
                        color: COLORS.text,
                      }}
                    >
                      <strong>{resultCount.toLocaleString("fr-FR")}</strong>{" "}
                      <span style={{ color: COLORS.textSecondary }}>résultats</span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Bramer explanation */}
            {queryElements.length > 0 && (
              <div
                style={{
                  marginTop: "28px",
                  padding: "16px",
                  borderRadius: "8px",
                  background: COLORS.surface,
                  border: `1px solid ${COLORS.border}`,
                }}
              >
                <p
                  style={{
                    fontFamily: fonts.body,
                    fontSize: "12px",
                    color: COLORS.textSecondary,
                    margin: 0,
                    lineHeight: 1.6,
                  }}
                >
                  Chaque concept ajouté combine les résultats avec{" "}
                  <span style={{ fontFamily: fonts.mono, fontWeight: 500 }}>AND</span>,
                  ce qui réduit le nombre d'articles. En recherche documentaire,
                  on commence large pour ne rien manquer, puis on affine si le volume
                  est trop important.
                </p>
                <p
                  style={{
                    fontFamily: fonts.body,
                    fontSize: "11px",
                    color: COLORS.textMuted,
                    margin: "8px 0 0 0",
                  }}
                >
                  Bramer et al., 2018 — J Med Libr Assoc
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
