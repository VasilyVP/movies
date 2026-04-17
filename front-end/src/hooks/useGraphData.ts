import { useQuery } from "@tanstack/react-query";
import { getFetcher } from "@/lib/utils";
import type { SearchResultItem } from "@/hooks/useSearch";

export type GraphQueryParams = {
  titleId?: string | null;
  nameId?: string | null;
  titleType?: string | null;
  genre?: string | null;
  ratingRangeFrom?: number | null;
  ratingRangeTo?: number | null;
  releaseYearFrom?: number | null;
  releaseYearTo?: number | null;
  topRated: boolean;
  mostPopular: boolean;
};

export type GraphFilters = {
  selectedSearchResult: SearchResultItem | null;
  titleType: string | null;
  genre: string | null;
  ratingRange: [number, number] | null;
  yearRange: [number, number] | null;
  topRated: boolean;
  mostPopular: boolean;
};

export type GraphNode = {
  id: string;
  type: "Title" | "Person";
  label: string;
  isAnchor?: boolean;
  score?: number;
  titleType?: string;
  genres?: string[];
  startYear?: number;
  averageRating?: number;
  numVotes?: number;
  primaryProfession?: string[];
  birthYear?: number;
  deathYear?: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  category?: string | null;
  job?: string | null;
  characters?: string[] | null;
  score?: number;
};

export type GraphMeta = {
  maxNodes: number;
  maxEdges: number;
  returnedNodes: number;
  returnedEdges: number;
  truncated: boolean;
};

export type GraphDataResponse = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: GraphMeta;
};

const GRAPH_DATA_QUERY_KEY = "graph-data";

function _toGraphQueryParams(filters: GraphFilters): GraphQueryParams {
  return {
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
}

export function useGraphData(filters: GraphFilters, requestToken: number) {
  const params = _toGraphQueryParams(filters);
  const enabled = requestToken > 0;

  return useQuery({
    queryKey: [GRAPH_DATA_QUERY_KEY, params, requestToken],
    queryFn: getFetcher<GraphDataResponse>("/query/graph-data", { params }),
    enabled,
  });
}
