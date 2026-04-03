import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./App.css";

export function Manifesto() {
	const [manifesto, setManifesto] = useState<string>("Ładowanie manifestu...");
	const [createdAt, setCreatedAt] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	const fetchManifesto = async () => {
		try {
			const res = await fetch(`/api/manifesto`);
			if (!res.ok) {
				throw new Error("Nie udało się pobrać manifestu z serwera");
			}
			const data = await res.json();
			setManifesto(data.content);
			if (data.created_at) {
				setCreatedAt(new Date(data.created_at).toLocaleString('pl-PL'));
			}
		} catch (error: any) {
			console.error("Error fetching manifesto:", error);
			setError(error.message || "Wystąpił błąd");
		}
	};

	useEffect(() => {
		fetchManifesto();
	}, []);

	return (
		<div className="container">
			<header>
				<h1 className="title">MANIFEST CWELA</h1>
				<nav>
					<Link to="/" className="nav-link" style={{ color: "white", textDecoration: "underline" }}>Powrót do cytatów</Link>
				</nav>
			</header>

			<main>
				<section className="manifesto-content" style={{ whiteSpace: "pre-wrap", textAlign: "left", padding: "2rem", backgroundColor: "#fff", color: "#000", borderRadius: "8px", marginTop: "1rem" }}>
					{error ? <p style={{ color: "red" }}>{error}</p> : manifesto}
				</section>
			</main>
		</div>
	);
}