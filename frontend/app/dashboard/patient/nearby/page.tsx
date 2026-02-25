"use client";

import { useCallback, useEffect, useState } from "react";
import {
  MapPin,
  Phone,
  Globe,
  Clock,
  Navigation,
  Loader2,
  AlertCircle,
  LocateFixed,
  RefreshCw,
} from "lucide-react";

import type { NearbyCareCenterLive, NearbyResponse } from "@/lib/data/types";

type LocationState =
  | { status: "idle" }
  | { status: "locating" }
  | { status: "loading"; lat: number; lon: number }
  | { status: "done"; data: NearbyResponse }
  | { status: "error"; message: string };

export default function PatientNearbyPage() {
  const [state, setState] = useState<LocationState>({ status: "idle" });
  const [radiusKm, setRadiusKm] = useState(15);

  const fetchNearby = useCallback(
    async (lat?: number, lon?: number) => {
      const params = new URLSearchParams();
      if (lat !== undefined && lon !== undefined) {
        params.set("lat", lat.toFixed(6));
        params.set("lon", lon.toFixed(6));
      }
      params.set("radius", String(radiusKm * 1000));

      setState(
        lat !== undefined && lon !== undefined
          ? { status: "loading", lat, lon }
          : { status: "locating" }
      );

      try {
        const resp = await fetch(`/api/nearby?${params.toString()}`);
        if (!resp.ok) throw new Error("Failed to fetch nearby centers");
        const data: NearbyResponse = await resp.json();
        setState({ status: "done", data });
      } catch (err) {
        setState({
          status: "error",
          message: err instanceof Error ? err.message : "Unknown error",
        });
      }
    },
    [radiusKm]
  );

  const requestLocation = useCallback(() => {
    if (!navigator.geolocation) {
      // No geolocation support → fall back to IP
      fetchNearby();
      return;
    }

    setState({ status: "locating" });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        fetchNearby(pos.coords.latitude, pos.coords.longitude);
      },
      () => {
        // Permission denied or error → use IP-based
        fetchNearby();
      },
      { enableHighAccuracy: false, timeout: 8000 }
    );
  }, [fetchNearby]);

  // Auto-trigger on mount
  useEffect(() => {
    requestLocation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Nearby Orthopedic Care
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Real-time results from your location.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Radius selector */}
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            value={radiusKm}
            onChange={(e) => setRadiusKm(Number(e.target.value))}
          >
            <option value={5}>5 km</option>
            <option value={10}>10 km</option>
            <option value={15}>15 km</option>
            <option value={25}>25 km</option>
            <option value={50}>50 km</option>
          </select>

          <button
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:opacity-50"
            disabled={state.status === "locating" || state.status === "loading"}
            onClick={requestLocation}
          >
            {state.status === "locating" || state.status === "loading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {/* Location badge */}
      {state.status === "done" && (
        <LocationBadge data={state.data} />
      )}

      {/* States */}
      {(state.status === "idle" || state.status === "locating") && (
        <div className="flex flex-col items-center justify-center gap-3 py-20">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Detecting your location…
          </p>
        </div>
      )}

      {state.status === "loading" && (
        <div className="flex flex-col items-center justify-center gap-3 py-20">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Searching for nearby orthopedic care…
          </p>
        </div>
      )}

      {state.status === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-red-200 bg-red-50 py-12 dark:border-red-800 dark:bg-red-950">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <p className="text-sm text-red-700 dark:text-red-300">
            {state.message}
          </p>
          <button
            className="mt-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            onClick={requestLocation}
          >
            Try Again
          </button>
        </div>
      )}

      {state.status === "done" && state.data.centers.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 py-12 dark:border-slate-700 dark:bg-slate-900">
          <MapPin className="h-8 w-8 text-slate-400" />
          <p className="text-sm text-slate-600 dark:text-slate-300">
            No orthopedic care centers found within {radiusKm} km.
          </p>
          <p className="text-xs text-slate-400">
            Try increasing the search radius.
          </p>
        </div>
      )}

      {state.status === "done" && state.data.centers.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {state.data.centers.map((center) => (
            <CenterCard key={center.id} center={center} />
          ))}
        </div>
      )}
    </main>
  );
}

/* ---------- Sub-components ---------- */

function LocationBadge({ data }: { data: NearbyResponse }) {
  const label =
    data.locationUsed === "gps"
      ? "GPS location"
      : data.locationUsed === "ip"
        ? "IP-based location"
        : "Default location";

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
      <LocateFixed className="h-3.5 w-3.5" />
      <span>{label}</span>
      <span className="text-slate-400">•</span>
      <span>
        {data.latitude.toFixed(4)}, {data.longitude.toFixed(4)}
      </span>
      <span className="text-slate-400">•</span>
      <span>{data.radiusKm} km radius</span>
      <span className="text-slate-400">•</span>
      <span className="font-medium">{data.centers.length} found</span>
    </div>
  );
}

function CenterCard({ center }: { center: NearbyCareCenterLive }) {
  const isOrtho = center.specialty.toLowerCase().includes("ortho");
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${center.latitude},${center.longitude}`;

  return (
    <article className="group relative flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900">
      {/* Ortho badge */}
      {isOrtho && (
        <span className="absolute right-4 top-4 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
          Orthopedic
        </span>
      )}

      <div className="space-y-3">
        {/* Name */}
        <h2 className="pr-20 text-lg font-semibold text-slate-900 dark:text-slate-100">
          {center.name}
        </h2>

        {/* Specialty */}
        <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
          {center.specialty}
        </p>

        {/* Distance */}
        <div className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
          <Navigation className="h-4 w-4 text-slate-400" />
          <span>{center.distanceKm} km away</span>
        </div>

        {/* Address */}
        {center.address && (
          <div className="flex items-start gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" />
            <span>{center.address}</span>
          </div>
        )}

        {/* Phone */}
        {center.phone && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <Phone className="h-4 w-4 text-slate-400" />
            <a
              className="underline decoration-slate-300 underline-offset-2 hover:text-blue-600 dark:decoration-slate-600 dark:hover:text-blue-400"
              href={`tel:${center.phone}`}
            >
              {center.phone}
            </a>
          </div>
        )}

        {/* Opening Hours */}
        {center.openingHours && (
          <div className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <Clock className="h-4 w-4 text-slate-400" />
            <span>{center.openingHours}</span>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
        <a
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-blue-700"
          href={mapsUrl}
          rel="noopener noreferrer"
          target="_blank"
        >
          <MapPin className="h-3.5 w-3.5" />
          Open in Maps
        </a>

        {center.website && (
          <a
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            href={center.website}
            rel="noopener noreferrer"
            target="_blank"
          >
            <Globe className="h-3.5 w-3.5" />
            Website
          </a>
        )}

        {center.phone && (
          <a
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            href={`tel:${center.phone}`}
          >
            <Phone className="h-3.5 w-3.5" />
            Call
          </a>
        )}
      </div>
    </article>
  );
}
