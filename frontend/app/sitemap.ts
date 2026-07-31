import type { MetadataRoute } from "next";
import { products, recipes } from "@/data/catalog";

const BASE_URL = "https://zerodang.org";

const staticRoutes = ["/", "/rooms", "/recipes", "/search", "/chat", "/login", "/signup", "/privacy", "/terms"];

export default function sitemap(): MetadataRoute.Sitemap {
  const staticEntries: MetadataRoute.Sitemap = staticRoutes.map((path) => ({
    url: `${BASE_URL}${path}`,
    changeFrequency: path === "/" ? "daily" : "weekly",
    priority: path === "/" ? 1 : 0.6,
  }));

  const productEntries: MetadataRoute.Sitemap = products.map((product) => ({
    url: `${BASE_URL}/product/${product.backendId ?? product.slug}`,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  const recipeEntries: MetadataRoute.Sitemap = recipes.map((recipe) => ({
    url: `${BASE_URL}/recipes/${recipe.databaseId ?? recipe.slug}`,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...staticEntries, ...productEntries, ...recipeEntries];
}
