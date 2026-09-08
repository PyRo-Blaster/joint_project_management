import { Skeleton } from "@/components/ui/skeleton";
import { ActivityFeed } from "./ActivityFeed";
import { Breakdowns } from "./Breakdowns";
import { NeedsAttention } from "./NeedsAttention";
import { StatTiles } from "./StatTiles";
import { useDashboard } from "./useDashboard";

export function DashboardPage() {
  const { data, isLoading, isError } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return <p className="text-sm text-danger">Could not load the dashboard.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      <StatTiles summary={data} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <NeedsAttention needs={data.needs_attention} />
          <Breakdowns byGroup={data.by_group} byOwnerOrg={data.by_owner_org} />
        </div>
        <ActivityFeed />
      </div>
    </div>
  );
}
