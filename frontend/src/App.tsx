import { useEffect, useState } from "react";
import "./App.css";

interface Quote {
	id: number;
	author: string;
	content: string;
}

function App() {
	const [quotes, setQuotes] = useState<Quote[]>([]);

	const fetchQuotes = async () => {
		try {
			const apiUrl =
				import.meta.env.VITE_API_URL ||
				`${window.location.protocol}//${window.location.hostname}:8000`;
			const res = await fetch(`${apiUrl}/quotes`);
			const data = await res.json();
			setQuotes(data);
		} catch (error) {
			console.error("Error fetching quotes:", error);
		}
	};
	useEffect(() => {
		fetchQuotes();
	}, []);

	return (
		<div className="container">
			<header>
				<h1 className="title">SIGMA QUOTES</h1>
				<p className="subtitle">
					Sigmastyczne cytaty z sigmastycznego discorda
				</p>
			</header>

			<main>
				<section className="quotes-list">
					{quotes.map(quote => (
						<div key={quote.id} className="quote-card">
							<p className="quote-content">"{quote.content}"</p>
							<p className="quote-author">- {quote.author}</p>
						</div>
					))}
					{quotes.length == 0 && <p className="no-quotes">Brak cytatów.</p>}
				</section>
			</main>
		</div>
	);
}

export default App;
