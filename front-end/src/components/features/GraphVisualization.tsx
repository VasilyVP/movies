import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

export function GraphVisualization() {
  return (
    <div className="h-full flex flex-col bg-neutral-950">
      {/* Toolbar */}
      <div className="h-12 border-b border-neutral-800 flex items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <Select defaultValue="force">
            <SelectTrigger className="w-40 h-8 bg-neutral-900 border-neutral-800">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="force">Force Layout</SelectItem>
              <SelectItem value="hierarchical">Hierarchical</SelectItem>
              <SelectItem value="circular">Circular</SelectItem>
              <SelectItem value="radial">Radial</SelectItem>
            </SelectContent>
          </Select>
          <Select defaultValue="all">
            <SelectTrigger className="w-40 h-8 bg-neutral-900 border-neutral-800">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Relationships</SelectItem>
              <SelectItem value="actors">Actors</SelectItem>
              <SelectItem value="directors">Directors</SelectItem>
              <SelectItem value="genres">Genres</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <Maximize2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="flex-1 relative bg-neutral-900/50">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-full border-2 border-neutral-700 border-dashed mx-auto flex items-center justify-center">
              <div className="w-6 h-6 rounded-full bg-neutral-700" />
            </div>
            <p className="text-sm text-neutral-500">Neo4j graph visualization area</p>
            <p className="text-xs text-neutral-600">Connect to display relationship networks</p>
          </div>
        </div>
      </div>

      {/* Stats Footer */}
      <div className="h-10 border-t border-neutral-800 flex items-center px-4 text-xs text-neutral-500">
        <div className="flex gap-6">
          <span>Nodes: <span className="text-neutral-300">0</span></span>
          <span>Edges: <span className="text-neutral-300">0</span></span>
          <span>Selected: <span className="text-neutral-300">None</span></span>
        </div>
      </div>
    </div>
  );
}
