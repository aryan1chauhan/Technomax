import { lazy, Suspense } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import RouteFallback from "../components/RouteFallback";

const MapWidget = lazy(() => import("../components/MapWidget"));

export default function MapPage() {
  const { state } = useLocation();
  const navigate = useNavigate();

  return (
    <Suspense fallback={<RouteFallback label="Loading live map..." />}>
      <MapWidget variant="dispatch" state={state} navigate={navigate} />
    </Suspense>
  );
}
