import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getFetcher } from "@/lib/utils";

export type ItemsFoundParams = {
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

export type ItemsFoundResponse = {
  totalTitles: number;
  totalPersons: number;
};

const ITEMS_FOUND_QUERY_KEY = "items-found";

export function useItemsFound(params: ItemsFoundParams) {
  return useQuery({
    queryKey: [ITEMS_FOUND_QUERY_KEY, params],
    queryFn: getFetcher<ItemsFoundResponse>("/query/items-found", { params }),
    placeholderData: keepPreviousData,
  });
}
