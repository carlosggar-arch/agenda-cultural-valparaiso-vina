# Representative event image fallback

When an event has no usable event-specific image, the public card UI may reuse a valid image from another event at the same normalized venue.

Policy:

- Event-specific images always take precedence.
- Generic agenda/cartelera images are never used as event images or as representative fallbacks.
- Representative images are matched only by normalized venue + city, never merely by source or category.
- Representative images are labelled `Imagen del recinto` and use representative alt text.
- If no reliable same-venue image exists, the category placeholder remains visible.
- The dataset is not mutated: the fallback is presentation-only and does not claim the representative photo belongs to the event.
- The same city-aware mechanism applies independently to Valparaíso/Viña and Gijón; images are never pooled across cities.
