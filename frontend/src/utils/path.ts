export const encodePathSegmentsForApi = (segments: string[]): string => {
  return segments.map((segment) => encodeURIComponent(segment)).join('/');
};

export const encodePathSegmentsForRoute = (segments: string[]): string => {
  return segments
    .map((segment) => encodeURIComponent(encodeURIComponent(segment)))
    .join('/');
};

export const decodeRoutePath = (path?: string): string[] => {
  if (!path) return [];
  // React Router already decodes the path param once, so we only need to decode once more
  // to undo our double-encoding
  const segments = path.split('/').filter((segment) => segment.trim().length > 0);
  
  // Try double-decode first (for our double-encoded segments)
  // If that doesn't work (produces URIError or still contains %), fall back to single decode
  return segments.map((segment) => {
    try {
      // Try double decode
      const onceDecoded = decodeURIComponent(segment);
      // Check if it still contains encoded characters - if so, we need another decode
      if (onceDecoded.includes('%')) {
        return decodeURIComponent(onceDecoded);
      }
      // If not, we might have been given a path that was already fully decoded
      // Try to detect if it needs a single decode by checking for common encoded patterns
      if (segment.includes('%') && segment.match(/%[0-9A-F]{2}/i)) {
        return decodeURIComponent(segment);
      }
      return onceDecoded;
    } catch (e) {
      // If double decode fails, try single decode
      try {
        return decodeURIComponent(segment);
      } catch (e2) {
        // If that also fails, return as-is (might already be decoded)
        return segment;
      }
    }
  });
};

