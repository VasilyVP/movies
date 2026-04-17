import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { useCallback, useEffect } from "react";
import { Filter, TrendingUp, Users } from "lucide-react";
import { useFilterOptions, type FilterOptionsResponse } from "@/hooks/useFilterOptions";
import { useItemsFound } from "@/hooks/useItemsFound";
import { useDebounce } from "@uidotdev/usehooks";
import { SearchAutocomplete } from "@/components/features/SearchAutocomplete";
import type { SearchResultItem } from "@/hooks/useSearch";
import loadingSpinner from "@/assets/loading-svgrepo-com.svg";

export type FilterState = {
  topRated: boolean;
  mostPopular: boolean;
  search: string;
  selectedSearchResult: SearchResultItem | null;
  genre: string | null;
  titleType: string | null;
  ratingRange: [number, number] | null;
  yearRange: [number, number] | null;
};

type FilterPanelProps = {
  filters: FilterState;
  setFilters: (updater: (draft: FilterState) => void) => void;
  onShowGraph: () => void;
  isGraphLoading: boolean;
  hasGraphRequested: boolean;
};

const quickQueries = [
  {
    icon: TrendingUp,
    label: "Top Rated",
    description: "Highest rated titles",
    toggle: "topRated" as const,
  },
  {
    icon: Users,
    label: "Most Popular",
    description: "By number of votes",
    toggle: "mostPopular" as const,
  },
];

const EMPTY_OPTIONS: FilterOptionsResponse = {
  genres: [],
  titleTypes: [],
  yearRange: { min: null, max: null },
  ratingRange: { min: null, max: null },
};

function clampRange(range: [number, number], min: number, max: number): [number, number] {
  const clampedMin = Math.min(Math.max(range[0], min), max);
  const clampedMax = Math.min(Math.max(range[1], min), max);
  return clampedMin <= clampedMax ? [clampedMin, clampedMax] : [clampedMax, clampedMin];
}

export function FilterPanel({
  filters,
  setFilters,
  onShowGraph,
  isGraphLoading,
  hasGraphRequested,
}: FilterPanelProps) {
  const handleToggleChange = useCallback(
    (toggle: "topRated" | "mostPopular", value: boolean) => {
      setFilters((draft) => {
        draft[toggle] = value;
      });
    },
    [setFilters],
  );

  const handleFieldChange = useCallback(
    <T extends keyof Omit<FilterState, "topRated" | "mostPopular">>(
      field: T,
      value: FilterState[T],
    ) => {
      setFilters((draft) => {
        draft[field] = value;
      });
    },
    [setFilters],
  );

  const handleOptionsRefresh = useCallback(
    (options: FilterOptionsResponse) => {
      setFilters((draft) => {
        const validGenres = new Set(options.genres);
        if (draft.genre && !validGenres.has(draft.genre)) {
          draft.genre = null;
        }

        const validTitleTypes = new Set(options.titleTypes.map((item) => item.value));
        if (draft.titleType && !validTitleTypes.has(draft.titleType)) {
          draft.titleType = null;
        }

        if (options.ratingRange.min !== null && options.ratingRange.max !== null) {
          if (draft.ratingRange === null) {
            draft.ratingRange = [options.ratingRange.min, options.ratingRange.max];
          } else {
            draft.ratingRange = clampRange(draft.ratingRange, options.ratingRange.min, options.ratingRange.max);
          }
        }

        if (options.yearRange.min !== null && options.yearRange.max !== null) {
          if (draft.yearRange === null) {
            draft.yearRange = [options.yearRange.min, options.yearRange.max];
          } else {
            draft.yearRange = clampRange(draft.yearRange, options.yearRange.min, options.yearRange.max);
          }
        }
      });
    },
    [setFilters],
  );

  const filterOptionsQuery = useFilterOptions({
    topRated: filters.topRated,
    mostPopular: filters.mostPopular,
  });

  const itemsFoundParams = {
    titleId: filters.selectedSearchResult?.primaryTitle ? filters.selectedSearchResult.id : null,
    nameId: filters.selectedSearchResult?.name ? filters.selectedSearchResult.id : null,
    titleType: filters.titleType,
    genre: filters.genre,
    ratingRangeFrom: filters.ratingRange?.[0] ?? null,
    ratingRangeTo: filters.ratingRange?.[1] ?? null,
    releaseYearFrom: filters.yearRange?.[0] ?? null,
    releaseYearTo: filters.yearRange?.[1] ?? null,
    topRated: filters.topRated,
    mostPopular: filters.mostPopular,
  };

  const debouncedItemsFoundParams = useDebounce(itemsFoundParams, 500);

  const itemsFoundQuery = useItemsFound(debouncedItemsFoundParams);
  const isItemsFoundLoading = itemsFoundQuery.isLoading || itemsFoundQuery.isFetching;

  useEffect(() => {
    if (filterOptionsQuery.data) {
      handleOptionsRefresh(filterOptionsQuery.data);
    }
  }, [filterOptionsQuery.data, handleOptionsRefresh]);

  const options = filterOptionsQuery.data ?? EMPTY_OPTIONS;

  const formatCount = (value: number | null | undefined): string => {
    return typeof value === "number" ? value.toLocaleString() : "N/A";
  };

  const totalTitles = itemsFoundQuery.data?.totalTitles;
  const totalPersons = itemsFoundQuery.data?.totalPersons;
  const areCountsAvailable = typeof totalTitles === "number" && typeof totalPersons === "number";
  const shouldDisableShowGraph = !areCountsAvailable || totalTitles > 1000 || totalPersons > 1000 || isGraphLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-neutral-400" />
        <h2 className="m-0 text-sm font-normal tracking-tight text-neutral-300">Filters</h2>
        {isItemsFoundLoading && (
          <span
            role="status"
            aria-label="Loading item counts"
            className="inline-flex h-4 w-4 items-center justify-center"
          >
            <img
              src={loadingSpinner}
              alt=""
              aria-hidden="true"
              className="h-4 w-4 animate-[spin_2.4s_linear_infinite]"
            />
          </span>
        )}
      </div>

      {/* Status */}
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 px-3 py-2">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-neutral-500">Titles Found</span>
            <span className="font-medium text-neutral-200">{formatCount(itemsFoundQuery.data?.totalTitles)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-neutral-500">Persons Found</span>
            <span className="font-medium text-neutral-200">{formatCount(itemsFoundQuery.data?.totalPersons)}</span>
          </div>
        </div>
      </div>

      {/* Search */}
      <SearchAutocomplete
        value={filters.search}
        onChange={(v) => handleFieldChange("search", v)}
        filters={filters}
        selectedItem={filters.selectedSearchResult}
        onSelect={(item) => setFilters((draft) => { draft.selectedSearchResult = item; })}
      />

      {/* Quick Queries */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Quick Queries</Label>
        <div className="grid grid-cols-2 gap-2">
          {quickQueries.map((query, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleToggleChange(query.toggle, !filters[query.toggle])}
              className={[
                "p-3 rounded-lg border transition-colors text-left",
                filters[query.toggle]
                  ? "border-neutral-500 bg-neutral-800/80"
                  : "border-neutral-800 bg-neutral-900/50 hover:bg-neutral-900 hover:border-neutral-700",
              ].join(" ")}
            >
              <query.icon className="w-4 h-4 text-neutral-400 mb-2" />
              <div className="text-xs text-neutral-300">{query.label}</div>
              <div className="text-[10px] text-neutral-600">{query.description}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Rating Range */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">IMDB Rating</Label>
        <div className="space-y-2">
          <Slider
            value={filters.ratingRange ?? [0, 10]}
            min={options.ratingRange.min ?? 0}
            max={options.ratingRange.max ?? 10}
            step={0.1}
            className="w-full"
            disabled={options.ratingRange.min === null || options.ratingRange.max === null}
            thumbLabels={[
              filters.ratingRange?.[0]?.toFixed(1) ?? "-",
              filters.ratingRange?.[1]?.toFixed(1) ?? "-",
            ]}
            onValueChange={(nextValue) => {
              if (nextValue.length >= 2) {
                handleFieldChange("ratingRange", [nextValue[0], nextValue[1]]);
              }
            }}
          />
          <div className="flex justify-between text-xs text-neutral-600">
            <span>{options.ratingRange.min?.toFixed(1) ?? "-"}</span>
            <span>{options.ratingRange.max?.toFixed(1) ?? "-"}</span>
          </div>
        </div>
      </div>

      {/* Year Range */}
      <div className="space-y-3">
        <Label className="text-xs text-neutral-400">Release Year</Label>
        <div className="space-y-2">
          <Slider
            value={filters.yearRange ?? [1900, 2024]}
            min={options.yearRange.min ?? 1900}
            max={options.yearRange.max ?? 2024}
            step={1}
            className="w-full"
            disabled={options.yearRange.min === null || options.yearRange.max === null}
            thumbLabels={[
              String(filters.yearRange?.[0] ?? "-"),
              String(filters.yearRange?.[1] ?? "-"),
            ]}
            onValueChange={(nextValue) => {
              if (nextValue.length >= 2) {
                handleFieldChange("yearRange", [Math.round(nextValue[0]), Math.round(nextValue[1])]);
              }
            }}
          />
          <div className="flex justify-between text-xs text-neutral-600">
            <span>{options.yearRange.min ?? "-"}</span>
            <span>{options.yearRange.max ?? "-"}</span>
          </div>
        </div>
      </div>

      {/* Genre + Type */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-3">
          <Label className="text-xs text-neutral-400">Genre</Label>
          <Select
            value={filters.genre ?? undefined}
            onValueChange={(value) => handleFieldChange("genre", value === "all" ? null : value)}
          >
            <SelectTrigger className="w-full bg-neutral-900 border-neutral-800">
              <SelectValue placeholder="All genres" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All genres</SelectItem>
              {options.genres.map((genre) => (
                <SelectItem key={genre} value={genre}>{genre}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label className="text-xs text-neutral-400">Type</Label>
          <Select
            value={filters.titleType ?? undefined}
            onValueChange={(value) => handleFieldChange("titleType", value === "all" ? null : value)}
          >
            <SelectTrigger className="w-full bg-neutral-900 border-neutral-800">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {options.titleTypes.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button
        size="lg"
        className="w-full"
        disabled={shouldDisableShowGraph}
        onClick={onShowGraph}
      >
        {isGraphLoading && (
          <img
            src={loadingSpinner}
            alt=""
            aria-hidden="true"
            className="mr-2 h-4 w-4 animate-[spin_2.4s_linear_infinite]"
          />
        )}
        {isGraphLoading ? "Building graph..." : hasGraphRequested ? "Update graph" : "Show graph"} {(!isGraphLoading && shouldDisableShowGraph) && "(<=1,000 items required)"}
      </Button>

    </div>
  );
}
