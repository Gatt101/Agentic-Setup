import { NextRequest, NextResponse } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const lat = searchParams.get("lat");
  const lon = searchParams.get("lon");
  const radius = searchParams.get("radius");

  const params = new URLSearchParams();
  if (lat) params.set("lat", lat);
  if (lon) params.set("lon", lon);
  if (radius) params.set("radius", radius);

  // Forward client IP for IP-based geolocation fallback
  const forwarded = req.headers.get("x-forwarded-for") ?? req.headers.get("x-real-ip") ?? "";

  try {
    const resp = await fetch(`${API_BASE}/nearby?${params.toString()}`, {
      headers: {
        "x-forwarded-for": forwarded,
      },
      cache: "no-store",
    });

    if (!resp.ok) {
      return NextResponse.json(
        { error: "Failed to fetch nearby care centers" },
        { status: resp.status }
      );
    }

    const data = await resp.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 502 }
    );
  }
}
