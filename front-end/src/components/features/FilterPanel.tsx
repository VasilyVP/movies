import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

export function FilterPanel() {
  return (
    <div className="space-y-6">
      {/* Year Range */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Release Year</Label>
        <div className="space-y-2">
          <Slider defaultValue={[1990, 2024]} min={1900} max={2024} step={1} className="w-full" />
          <div className="flex justify-between text-xs text-neutral-500">
            <span>1990</span>
            <span>2024</span>
          </div>
        </div>
      </div>

      {/* Rating Range */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">IMDB Rating</Label>
        <div className="space-y-2">
          <Slider defaultValue={[7.0, 9.0]} min={0} max={10} step={0.1} className="w-full" />
          <div className="flex justify-between text-xs text-neutral-500">
            <span>7.0</span>
            <span>9.0</span>
          </div>
        </div>
      </div>

      {/* Genre */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Genre</Label>
        <Select>
          <SelectTrigger className="bg-neutral-900 border-neutral-800">
            <SelectValue placeholder="All genres" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All genres</SelectItem>
            <SelectItem value="action">Action</SelectItem>
            <SelectItem value="comedy">Comedy</SelectItem>
            <SelectItem value="drama">Drama</SelectItem>
            <SelectItem value="horror">Horror</SelectItem>
            <SelectItem value="scifi">Sci-Fi</SelectItem>
            <SelectItem value="thriller">Thriller</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Content Type */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Type</Label>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox id="movies" defaultChecked />
            <label htmlFor="movies" className="text-sm text-neutral-300 cursor-pointer">Movies</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="series" defaultChecked />
            <label htmlFor="series" className="text-sm text-neutral-300 cursor-pointer">TV Series</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="episodes" />
            <label htmlFor="episodes" className="text-sm text-neutral-300 cursor-pointer">Episodes</label>
          </div>
        </div>
      </div>

      {/* Language */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Language</Label>
        <Select>
          <SelectTrigger className="bg-neutral-900 border-neutral-800">
            <SelectValue placeholder="All languages" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All languages</SelectItem>
            <SelectItem value="en">English</SelectItem>
            <SelectItem value="es">Spanish</SelectItem>
            <SelectItem value="fr">French</SelectItem>
            <SelectItem value="de">German</SelectItem>
            <SelectItem value="ja">Japanese</SelectItem>
            <SelectItem value="ko">Korean</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button className="flex-1" size="sm">Apply Filters</Button>
        <Button variant="outline" size="sm" className="border-neutral-800">
          <X className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
