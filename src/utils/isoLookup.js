// Numeric ISO 3166-1 → alpha-3 mapping (for TopoJSON ↔ IndexedDB bridge)
const NUMERIC_TO_ALPHA3 = {
  4: 'AFG', 8: 'ALB', 12: 'DZA', 24: 'AGO', 32: 'ARG', 36: 'AUS',
  40: 'AUT', 50: 'BGD', 56: 'BEL', 64: 'BTN', 68: 'BOL', 76: 'BRA',
  100: 'BGR', 104: 'MMR', 116: 'KHM', 120: 'CMR', 124: 'CAN', 144: 'LKA',
  152: 'CHL', 156: 'CHN', 170: 'COL', 180: 'COD', 188: 'CRI', 191: 'HRV',
  192: 'CUB', 196: 'CYP', 203: 'CZE', 208: 'DNK', 214: 'DOM', 218: 'ECU',
  818: 'EGY', 222: 'SLV', 231: 'ETH', 246: 'FIN', 250: 'FRA', 266: 'GAB',
  276: 'DEU', 288: 'GHA', 300: 'GRC', 320: 'GTM', 332: 'HTI', 340: 'HND',
  348: 'HUN', 356: 'IND', 360: 'IDN', 364: 'IRN', 368: 'IRQ', 372: 'IRL',
  376: 'ISR', 380: 'ITA', 388: 'JAM', 392: 'JPN', 400: 'JOR', 398: 'KAZ',
  404: 'KEN', 408: 'PRK', 410: 'KOR', 414: 'KWT', 417: 'KGZ', 418: 'LAO',
  422: 'LBN', 430: 'LBR', 434: 'LBY', 440: 'LTU', 442: 'LUX', 450: 'MDG',
  458: 'MYS', 466: 'MLI', 484: 'MEX', 496: 'MNG', 504: 'MAR', 508: 'MOZ',
  516: 'NAM', 524: 'NPL', 528: 'NLD', 554: 'NZL', 558: 'NIC', 562: 'NER',
  566: 'NGA', 578: 'NOR', 586: 'PAK', 591: 'PAN', 598: 'PNG', 600: 'PRY',
  604: 'PER', 608: 'PHL', 616: 'POL', 620: 'PRT', 630: 'PRI', 634: 'QAT',
  642: 'ROU', 643: 'RUS', 646: 'RWA', 682: 'SAU', 686: 'SEN', 694: 'SLE',
  703: 'SVK', 706: 'SOM', 710: 'ZAF', 724: 'ESP', 729: 'SDN',
  752: 'SWE', 756: 'CHE', 760: 'SYR', 762: 'TJK', 764: 'THA', 768: 'TGO',
  780: 'TTO', 788: 'TUN', 792: 'TUR', 800: 'UGA', 804: 'UKR', 784: 'ARE',
  826: 'GBR', 840: 'USA', 858: 'URY', 860: 'UZB', 862: 'VEN', 704: 'VNM',
  887: 'YEM', 894: 'ZMB', 716: 'ZWE', 51: 'ARM', 31: 'AZE', 112: 'BLR',
  70: 'BIH', 854: 'BFA', 108: 'BDI', 132: 'CPV', 140: 'CAF', 148: 'TCD',
  174: 'COM', 178: 'COG', 262: 'DJI', 232: 'ERI', 233: 'EST', 238: 'FLK',
  242: 'FJI', 270: 'GMB', 268: 'GEO', 324: 'GIN', 226: 'GNQ', 624: 'GNB',
  328: 'GUY', 352: 'ISL', 426: 'LSO', 428: 'LVA', 454: 'MWI', 474: 'MTQ',
  478: 'MRT', 480: 'MUS', 498: 'MDA', 540: 'NCL', 570: 'NIU',
  585: 'PLW', 275: 'PSE', 659: 'KNA',
  662: 'LCA', 670: 'VCT', 882: 'WSM', 674: 'SMR', 678: 'STP', 688: 'SRB',
  690: 'SYC', 748: 'SWZ', 626: 'TLS',
  796: 'TCA', 798: 'TUV', 807: 'MKD', 850: 'VIR', 876: 'WLF',
  834: 'TZA', 728: 'SSD', 732: 'ESH', 158: 'TWN',
};

const ALPHA3_TO_NUMERIC = {};
for (const [num, a3] of Object.entries(NUMERIC_TO_ALPHA3)) {
  ALPHA3_TO_NUMERIC[a3] = parseInt(num, 10);
}

export function numericToAlpha3(numericId) {
  return NUMERIC_TO_ALPHA3[numericId] || null;
}

export function alpha3ToNumeric(alpha3) {
  return ALPHA3_TO_NUMERIC[alpha3] || null;
}
