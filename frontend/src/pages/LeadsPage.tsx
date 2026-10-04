import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listRestaurants,
  type RestaurantFilters,
} from "../api/endpoints";
import type {
  DeliveryPlatform,
  LeadStatus,
  Page,
  RestaurantRow,
  SourceType,
} from "../api/types";
import LeadDrawer from "../components/LeadDrawer";
import ScoreCell from "../components/ScoreCell";
import StatusBadge from "../components/StatusBadge";
import {
  LEAD_STATUS_INFO,
  PLATFORM_LABELS,
  SOURCE_LABELS,
} from "../lib/labels";
import { formatDate } from "../lib/format";

const SELECT_CLASS =
  "rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100";
const INPUT_CLASS =
  "rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-100";

const SCORE_RANGES = [
  { value: "", label: "Score: todos" },
  { value: "40", label: "Score ≥ 40" },
  { value: "60", label: "Score ≥ 60" },
  { value: "80", label: "Score ≥ 80" },
];

export default function LeadsPage() {
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<Page<RestaurantRow> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Filters (initial search preloaded from the dashboard links).
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState<LeadStatus | "">("");
  const [platform, setPlatform] = useState<DeliveryPlatform | "">("");
  const [source, setSource] = useState<SourceType | "">("");
  const [minScore, setMinScore] = useState("");
  const [sort, setSort] = useState<"score" | "name" | "updated_at">("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(timer);
  }, [search]);

  const filters: RestaurantFilters = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      city: city || undefined,
      category: category || undefined,
      status: status || undefined,
      platform: platform || undefined,
      source: source || undefined,
      min_score: minScore ? Number(minScore) : undefined,
      sort,
      order,
      page,
      page_size: pageSize,
    }),
    [debouncedSearch, city, category, status, platform, source, minScore, sort, order, page],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await listRestaurants(filters));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando leads");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load, reloadKey]);

  function clearFilters() {
    setSearch("");
    setCity("");
    setCategory("");
    setStatus("");
    setPlatform("");
    setSource("");
    setMinScore("");
    setSort("score");
    setOrder("desc");
    setPage(1);
  }

  function refresh() {
    setReloadKey((key) => key + 1);
  }

  const total = rows?.total ?? 0;
  const firstItem = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const lastItem = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Leads</h1>
          <p className="mt-1 text-sm text-slate-500">
            {loading ? "Cargando…" : `${total} restaurantes`}
          </p>
        </div>
        <button
          onClick={refresh}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-slate-50"
        >
          ↻ Actualizar
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar nombre o teléfono…"
          className={`${INPUT_CLASS} w-56`}
        />
        <input
          value={city}
          onChange={(e) => {
            setCity(e.target.value);
            setPage(1);
          }}
          placeholder="Ciudad"
          className={`${INPUT_CLASS} w-32`}
        />
        <input
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(1);
          }}
          placeholder="Categoría"
          className={`${INPUT_CLASS} w-32`}
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as LeadStatus | "");
            setPage(1);
          }}
          className={SELECT_CLASS}
        >
          <option value="">Estado: todos</option>
          {Object.entries(LEAD_STATUS_INFO).map(([value, info]) => (
            <option key={value} value={value}>
              {info.label}
            </option>
          ))}
        </select>
        <select
          value={platform}
          onChange={(e) => {
            setPlatform(e.target.value as DeliveryPlatform | "");
            setPage(1);
          }}
          className={SELECT_CLASS}
        >
          <option value="">Plataforma: todas</option>
          {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={source}
          onChange={(e) => {
            setSource(e.target.value as SourceType | "");
            setPage(1);
          }}
          className={SELECT_CLASS}
        >
          <option value="">Fuente: todas</option>
          {Object.entries(SOURCE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={minScore}
          onChange={(e) => {
            setMinScore(e.target.value);
            setPage(1);
          }}
          className={SELECT_CLASS}
        >
          {SCORE_RANGES.map((range) => (
            <option key={range.value} value={range.value}>
              {range.label}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
          className={SELECT_CLASS}
        >
          <option value="score">Ordenar: score</option>
          <option value="updated_at">Ordenar: actualización</option>
          <option value="name">Ordenar: nombre</option>
        </select>
        <button
          onClick={() => setOrder(order === "desc" ? "asc" : "desc")}
          className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
          title={order === "desc" ? "Descendente" : "Ascendente"}
        >
          {order === "desc" ? "↓" : "↑"}
        </button>
        <button
          onClick={clearFilters}
          className="ml-auto rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-800"
        >
          Limpiar
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Nombre</th>
                <th className="px-4 py-3">Zona</th>
                <th className="px-4 py-3">Teléfono</th>
                <th className="px-4 py-3">Delivery</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Último contacto</th>
                <th className="px-4 py-3">Próximo seguim.</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-400">
                    Cargando…
                  </td>
                </tr>
              )}
              {!loading && rows?.items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-400">
                    Sin resultados con estos filtros.
                  </td>
                </tr>
              )}
              {!loading &&
                rows?.items.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className="cursor-pointer transition hover:bg-slate-50"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{row.name}</div>
                      {row.category && (
                        <div className="text-xs text-slate-400">{row.category}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{row.city ?? "—"}</td>
                    <td className="px-4 py-3 tabular-nums text-slate-600">
                      {row.phone ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      {row.delivery_platforms.length === 0 ? (
                        <span className="text-xs text-slate-400">no</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {row.delivery_platforms.map((p) => (
                            <span
                              key={p}
                              className="rounded-md bg-teal-50 px-1.5 py-0.5 text-xs font-medium text-teal-700"
                            >
                              {PLATFORM_LABELS[p as DeliveryPlatform] ?? p}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreCell
                        score={row.lead?.score ?? null}
                        reasons={row.lead?.score_reasons}
                      />
                    </td>
                    <td className="px-4 py-3">
                      {row.lead && <StatusBadge status={row.lead.status} />}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(row.last_interaction_at)}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(row.next_follow_up_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        {row.phone && (
                          <a
                            href={`tel:${row.phone}`}
                            onClick={(e) => e.stopPropagation()}
                            title="Llamar"
                            className="rounded-lg border border-slate-200 px-2 py-1 text-xs transition hover:bg-teal-50 hover:text-teal-700"
                          >
                            📞
                          </a>
                        )}
                        {row.phone && (
                          <a
                            href={`https://wa.me/${row.phone.replace(/[^0-9]/g, "")}`}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            title="WhatsApp"
                            className="rounded-lg border border-slate-200 px-2 py-1 text-xs transition hover:bg-emerald-50"
                          >
                            💬
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm text-slate-500">
          <span>
            {total > 0
              ? `${firstItem}–${lastItem} de ${total}`
              : "Sin resultados"}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
            >
              ← Anterior
            </button>
            <button
              onClick={() => setPage((p) => (lastItem < total ? p + 1 : p))}
              disabled={lastItem >= total}
              className="rounded-lg border border-slate-200 px-3 py-1.5 font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
            >
              Siguiente →
            </button>
          </div>
        </div>
      </div>

      {/* Drawer (open lead -> see -> contact -> register -> schedule) */}
      {selectedId && (
        <LeadDrawer
          restaurantId={selectedId}
          onClose={() => setSelectedId(null)}
          onChanged={refresh}
        />
      )}
    </div>
  );
}
