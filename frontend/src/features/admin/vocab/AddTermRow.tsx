import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AddTermRow({
  onAdd,
  pending,
}: {
  onAdd: (value: string) => void;
  pending: boolean;
}) {
  const [value, setValue] = useState("");
  const add = () => {
    if (value.trim()) {
      onAdd(value.trim());
      setValue("");
    }
  };
  return (
    <div className="flex items-center gap-2">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="New term…"
        className="h-8 w-56"
        onKeyDown={(e) => e.key === "Enter" && add()}
      />
      <Button size="sm" disabled={!value.trim() || pending} onClick={add}>
        <Plus className="size-4" /> Add
      </Button>
    </div>
  );
}
