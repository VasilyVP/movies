import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BarChart3, TrendingUp, Users, Award } from "lucide-react";

const quickQueries = [
  { icon: TrendingUp, label: "Top Rated", description: "Highest rated titles" },
  { icon: Users, label: "Most Popular", description: "By number of votes" },
  { icon: Award, label: "Award Winners", description: "Oscar & Emmy winners" },
  { icon: BarChart3, label: "Trending", description: "Recent popularity surge" },
];

export function QueryPanel() {
  return (
    <div className="space-y-6">
      {/* Quick Queries */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Quick Queries</Label>
        <div className="grid grid-cols-2 gap-2">
          {quickQueries.map((query, idx) => (
            <button
              key={idx}
              className="p-3 rounded-lg border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-900 hover:border-neutral-700 transition-colors text-left"
            >
              <query.icon className="w-4 h-4 text-neutral-400 mb-2" />
              <div className="text-xs text-neutral-300">{query.label}</div>
              <div className="text-[10px] text-neutral-600">{query.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Aggregation Builder */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Aggregation</Label>
        <div className="space-y-2">
          <Select defaultValue="count">
            <SelectTrigger className="bg-neutral-900 border-neutral-800">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="count">COUNT</SelectItem>
              <SelectItem value="avg">AVG</SelectItem>
              <SelectItem value="sum">SUM</SelectItem>
              <SelectItem value="min">MIN</SelectItem>
              <SelectItem value="max">MAX</SelectItem>
            </SelectContent>
          </Select>
          <Select defaultValue="rating">
            <SelectTrigger className="bg-neutral-900 border-neutral-800">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="rating">Rating</SelectItem>
              <SelectItem value="votes">Number of Votes</SelectItem>
              <SelectItem value="runtime">Runtime</SelectItem>
              <SelectItem value="year">Year</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Group By */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Group By</Label>
        <Select defaultValue="genre">
          <SelectTrigger className="bg-neutral-900 border-neutral-800">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="genre">Genre</SelectItem>
            <SelectItem value="year">Year</SelectItem>
            <SelectItem value="director">Director</SelectItem>
            <SelectItem value="actor">Main Actor</SelectItem>
            <SelectItem value="language">Language</SelectItem>
            <SelectItem value="country">Country</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Custom Query */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Custom Query</Label>
        <Input
          placeholder="Enter SQL-like query..."
          className="bg-neutral-900 border-neutral-800 font-mono text-xs"
        />
      </div>

      {/* Execute Button */}
      <Button className="w-full" size="sm">Execute Query</Button>

      {/* Results Preview */}
      <div className="space-y-2">
        <Label className="text-xs text-neutral-400">Results</Label>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/30 p-3">
          <div className="text-xs text-neutral-500 text-center py-4">No results yet</div>
        </div>
      </div>
    </div>
  );
}
