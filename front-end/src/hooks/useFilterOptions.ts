import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getFetcher } from "@/lib/utils";

export type TitleTypeOption = {
  value: string;
  label: string;
};

export type NumericRangeInt = {
  min: number | null;
  max: number | null;
};

export type NumericRangeFloat = {
  min: number | null;
  max: number | null;
};

export type FilterOptionsResponse = {
  genres: string[];
  titleTypes: TitleTypeOption[];
  yearRange: NumericRangeInt;
  ratingRange: NumericRangeFloat;
};

export type FilterOptionsToggles = {
  topRated: boolean;
  mostPopular: boolean;
};

const FILTER_OPTIONS_QUERY_KEY = "filter-options";

export function useFilterOptions(toggles: FilterOptionsToggles) {
  return useQuery({
    queryKey: [FILTER_OPTIONS_QUERY_KEY, toggles.topRated, toggles.mostPopular],
    queryFn: getFetcher<FilterOptionsResponse>("/query/filter-options", { params: toggles }),
    placeholderData: keepPreviousData,
  });
}
