import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Game, GameServer } from "./types";
import { GameCard } from "./components/GameCard";
import { DeployModal } from "./components/DeployModal";
import { ServerCard } from "./components/ServerCard";

type Toast = { id: number; kind: "ok" | "err"; text: string };

export default function App() {
  const [games, setGames] = useState<Game[]>([]);
  const [servers, setServers] = useState<GameServer[]>([]);
  const [provider, setProvider] = useState<string>("");
  const [online, setOnline] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<Game | null>(null);
  const [deployBusy, setDeployBusy] = useState(false);
  const [deployErr, setDeployErr] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Record<string, boolean>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);

  const gamesById = useMemo(() => {
    const m: Record<string, Game> = {};
    for (const g of games) m[g.id] = g;
    return m;
  }, [games]);

  const pushToast = useCallback((kind: Toast["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  // Initial load: health + catalog.
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setOnline(true);
        setProvider(h.provider);
      })
      .catch(() => setOnline(false));
    api
      .games()
      .then(setGames)
      .catch(() => pushToast("err", "Failed to load game catalog"));
  }, [pushToast]);

  // Poll server list every 2s.
  const refreshServers = useCallback(async () => {
    try {
      const list = await api.servers();
      setServers(list.sort((a, b) => (a.createdAt ?? "").localeCompare(b.createdAt ?? "")));
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refreshServers();
    const t = setInterval(refreshServers, 2000);
    return () => clearInterval(t);
  }, [refreshServers]);

  const deploy = async (payload: {
    name: string;
    game: string;
    options: Record<string, unknown>;
  }) => {
    setDeployBusy(true);
    setDeployErr(null);
    try {
      await api.createServer(payload);
      pushToast("ok", `Deploying ${payload.name}…`);
      setSelected(null);
      refreshServers();
    } catch (e) {
      setDeployErr(e instanceof Error ? e.message : "Deploy failed");
    } finally {
      setDeployBusy(false);
    }
  };

  const remove = async (name: string) => {
    setDeleting((d) => ({ ...d, [name]: true }));
    try {
      await api.deleteServer(name);
      pushToast("ok", `Deleted ${name}`);
      setServers((s) => s.filter((x) => x.name !== name));
    } catch (e) {
      pushToast("err", e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting((d) => {
        const { [name]: _, ...rest } = d;
        return rest;
      });
    }
  };

  const running = servers.filter((s) => s.status.phase === "Running").length;

  return (
    <div className="mx-auto min-h-full max-w-6xl px-5 pb-24 pt-8">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-4 pb-8">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-2xl shadow-lg">
            🦤
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight text-white">
              Quetzel<span className="text-brand-400">Panel</span>
            </h1>
            <p className="text-xs text-white/45">One-click game servers on Kubernetes</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5">
            <span
              className={"h-2 w-2 rounded-full " + (online ? "dot-pulse" : "")}
              style={{ background: online ? "#2dd4a7" : online === false ? "#f87171" : "#fbbf24" }}
            />
            {online ? "API online" : online === false ? "API offline" : "connecting…"}
          </span>
          {provider && (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-white/60">
              provider: <span className="font-semibold text-brand-400">{provider}</span>
            </span>
          )}
        </div>
      </header>

      {/* game library */}
      <section className="pb-10">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-bold text-white">Game Library</h2>
          <span className="text-xs text-white/40">{games.length} games available</span>
        </div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {games.map((g) => (
            <GameCard key={g.id} game={g} onDeploy={setSelected} />
          ))}
          {games.length === 0 && (
            <div className="col-span-full rounded-2xl border border-dashed border-white/10 p-10 text-center text-white/40">
              Loading catalog…
            </div>
          )}
        </div>
      </section>

      {/* my servers */}
      <section>
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-bold text-white">My Servers</h2>
          <span className="text-xs text-white/40">
            {servers.length} total · {running} running
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {servers.map((s) => (
            <ServerCard
              key={s.name}
              server={s}
              game={gamesById[s.spec.game]}
              onDelete={remove}
              deleting={!!deleting[s.name]}
            />
          ))}
          {servers.length === 0 && (
            <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-white/40">
              No servers yet — pick a game above and hit Deploy.
            </div>
          )}
        </div>
      </section>

      {/* deploy modal */}
      {selected && (
        <DeployModal
          game={selected}
          busy={deployBusy}
          error={deployErr}
          onClose={() => {
            setSelected(null);
            setDeployErr(null);
          }}
          onSubmit={deploy}
        />
      )}

      {/* toasts */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="fade-in rounded-xl border px-4 py-2.5 text-sm shadow-lg"
            style={{
              borderColor: t.kind === "ok" ? "#2dd4a733" : "#f8717133",
              background: t.kind === "ok" ? "rgba(45,212,167,0.12)" : "rgba(248,113,113,0.12)",
              color: t.kind === "ok" ? "#6ee7c7" : "#fca5a5",
            }}
          >
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
