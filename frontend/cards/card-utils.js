export function itemId(item) {
  return item?.item_id ?? item?.id;
}

export function dinnerItems(dinner) {
  return dinner?.items ?? [];
}

export function cardStrings(language) {
  return language?.toLowerCase().split('-')[0] === 'nl' ? 'nl' : 'en';
}
