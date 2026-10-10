// Texture UVs use a bottom-left origin; source raster rows start at the north.
export function cellImageUV(cell, imagery){
 const tile=imagery?.cells?.find(c=>c.lat===cell.lat&&c.lng===cell.lng);
 if(!tile||!imagery.cellRows||!imagery.cellColumns)return null;
 return {u0:tile.column/imagery.cellColumns,u1:(tile.column+1)/imagery.cellColumns,
  v0:1-(tile.row+1)/imagery.cellRows,v1:1-tile.row/imagery.cellRows};
}

export function textureSources(imagery, appearance='original'){
 if(!imagery?.image)return [];
 const preferred=appearance==='ai'&&imagery.superResolution?.status==='ready'&&imagery.superResolution?.displayOnly===true
  ?imagery.superResolvedImage:appearance==='enhanced'?imagery.enhancedImage:null;
 return [...new Set([preferred,imagery.image].filter(Boolean))];
}
